from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class AccountCashMoveReason(models.Model):
    _name = 'account.cash.move.reason'
    _description = "Type d'operation de caisse"
    _order = 'name'

    name = fields.Char(string='Libelle', required=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )
    account_id = fields.Many2one('account.account', string='Compte')
    move_type = fields.Selection([
        ('in', 'Entree'),
        ('out', 'Sortie'),
    ], string='Type', default='out')
    active = fields.Boolean(default=True)

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    cash_move_reason_id = fields.Many2one(
        'account.cash.move.reason',
        string="Type d'operation",
    )
    is_internal_transfer = fields.Boolean(
        string='Transfert interne',
        default=False,
    )
    destination_journal_id = fields.Many2one(
        'account.journal',
        string='Journal de destination',
        domain="[('type', 'in', ['bank', 'cash']), ('id', '!=', journal_id)]",
    )
    ecriture_line_ids = fields.One2many(
        'account.move.line',
        related='move_id.line_ids',
        string='Lignes comptables',
        readonly=True,
    )
    compte_contrepartie_id = fields.Many2one(
        'account.account',
        string='Compte',
        compute='_compute_compte_contrepartie',
        store=True,
    )

    @api.depends('move_id.line_ids.account_id')
    def _compute_compte_contrepartie(self):
        for payment in self:
            compte = False
            for line in payment.move_id.line_ids:
                if line.account_id.account_type not in ('asset_cash',):
                    compte = line.account_id
                    break
            payment.compte_contrepartie_id = compte

    @api.onchange('is_internal_transfer')
    def _onchange_is_internal_transfer(self):
        if not self.is_internal_transfer:
            self.destination_journal_id = False

    def action_post(self):
        res = super().action_post()
        for payment in self:
            payment._fix_move_accounts()
            payment._clean_move_line_names()

            if (payment.is_internal_transfer
                    and payment.destination_journal_id
                    and not payment.paired_internal_transfer_payment_id):

                dest_journal = payment.destination_journal_id
                dest_payment_method_line = self.env[
                    'account.payment.method.line'
                ].search([
                    ('journal_id', '=', dest_journal.id),
                ], limit=1)

                counterpart_type = (
                    'inbound' if payment.payment_type == 'outbound'
                    else 'outbound'
                )

                counterpart_vals = {
                    'journal_id': dest_journal.id,
                    'destination_journal_id': payment.journal_id.id,
                    'payment_type': counterpart_type,
                    'partner_id': payment.partner_id.id,
                    'amount': payment.amount,
                    'date': payment.date,
                    'memo': payment.memo,
                    'is_internal_transfer': True,
                    'paired_internal_transfer_payment_id': payment.id,
                    'payment_method_line_id': (
                        dest_payment_method_line.id
                        if dest_payment_method_line else False
                    ),
                }

                counterpart = self.env['account.payment'].create(
                    counterpart_vals
                )
                counterpart.action_post()
                payment.paired_internal_transfer_payment_id = counterpart.id
        return res

    def _fix_move_accounts(self):
        """Fix partie double : reaffecte la ligne de contrepartie sur le
        compte du type d'operation choisi (ou sur le compte par defaut du
        journal de destination pour un transfert interne)."""
        self.ensure_one()
        move = self.move_id
        if not move:
            return

        counterpart_account = False
        if (self.cash_move_reason_id
                and self.cash_move_reason_id.account_id):
            counterpart_account = self.cash_move_reason_id.account_id
        elif self.is_internal_transfer and self.destination_journal_id:
            counterpart_account = (
                self.destination_journal_id.default_account_id
            )

        if not counterpart_account:
            return

        if self.payment_type == 'outbound':
            counterpart_line = move.line_ids.filtered(
                lambda l: l.debit > 0
            )
        else:
            counterpart_line = move.line_ids.filtered(
                lambda l: l.credit > 0
            )

        if not counterpart_line:
            return

        counterpart_line = counterpart_line[0]

        if counterpart_line.account_id == counterpart_account:
            return

        _logger.info(
            'CASH_MOVE_REASON: fix %s -> compte %s remplace par %s',
            self.name,
            counterpart_line.account_id.display_name,
            counterpart_account.display_name,
        )
        move.button_draft()
        counterpart_line.with_context(
            skip_account_move_synchronization=True
        ).write({
            'account_id': counterpart_account.id,
        })
        move.action_post()

    def _clean_move_line_names(self):
        """Supprimer le prefixe Paiement manuel: des libelles."""
        self.ensure_one()
        if not self.move_id:
            return
        for line in self.move_id.line_ids:
            if line.name and 'Paiement manuel:' in line.name:
                clean_name = line.name.replace('Paiement manuel:', '').strip()
                line.with_context(
                    skip_account_move_synchronization=True
                ).write({'name': clean_name})
