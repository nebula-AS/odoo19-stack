from odoo import models, fields

class CashBrouillardWizard(models.TransientModel):
    _name = 'cash.brouillard.wizard'
    _description = 'Assistant Brouillard de Caisse'

    journal_id = fields.Many2one(
        'account.journal',
        string='Caisse',
        domain=[('type', '=', 'cash')],
        required=True,
        default=lambda self: self.env['account.journal'].sudo().search(
            [('type', '=', 'cash')], order='id asc', limit=1
        )
    )
    date_debut = fields.Date(string='Date Debut', required=True, default=fields.Date.context_today)
    date_fin = fields.Date(string='Date Fin', required=True, default=fields.Date.context_today)

    def _get_solde_ouverture(self):
        lines = self.env['account.move.line'].sudo().search([
            ('journal_id', '=', self.journal_id.id),
            ('date', '<', self.date_debut),
            ('parent_state', '=', 'posted'),
            ('account_id.account_type', '=', 'asset_cash'),
        ])
        return sum(l.debit - l.credit for l in lines)

    def _get_lines(self):
        return self.env['account.move.line'].sudo().search([
            ('journal_id', '=', self.journal_id.id),
            ('date', '>=', self.date_debut),
            ('date', '<=', self.date_fin),
            ('parent_state', '=', 'posted'),
            ('account_id.account_type', '=', 'asset_cash'),
        ], order='date asc, id asc')

    def action_afficher(self):
        self.ensure_one()
        return {
            'name': 'Brouillard de caisse',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': [
                ('journal_id', '=', self.journal_id.id),
                ('date', '>=', self.date_debut),
                ('date', '<=', self.date_fin),
                ('parent_state', '=', 'posted'),
                ('account_id.account_type', '=', 'asset_cash'),
            ],
            'context': {
                'default_journal_id': self.journal_id.id,
                'create': False,
            },
            'target': 'current',
        }

    def action_imprimer_pdf(self):
        lines = self._get_lines()
        solde_ouverture = self._get_solde_ouverture()
        solde = solde_ouverture
        lines_data = []
        for line in lines:
            solde += line.debit - line.credit
            lines_data.append({
                'ref': line.move_id.name or '',
                'date': str(line.date),
                'libelle': line.name or line.move_id.ref or '',
                'debit': line.debit,
                'credit': line.credit,
                'solde': solde,
            })
        data = {
            'journal_name': self.journal_id.name,
            'date_debut': str(self.date_debut),
            'date_fin': str(self.date_fin),
            'solde_ouverture': solde_ouverture,
            'lines': lines_data,
            'total_debit': sum(l['debit'] for l in lines_data),
            'total_credit': sum(l['credit'] for l in lines_data),
            'solde_final': solde_ouverture + sum(l['debit'] - l['credit'] for l in lines),
        }
        return self.env.ref(
            'account_cash_move_reason.action_report_cash_brouillard'
        ).report_action(self, data=data)
