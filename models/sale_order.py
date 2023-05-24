# Copyright (C) 2017 - Today: GRAP (http://www.grap.coop)
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, models
#from datetime import datetime
import logging
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model
    def _prepare_from_pos(self, order_data):
        PosSession = self.env["pos.session"]
        session = PosSession.browse(order_data["pos_session_id"])
        return {
            "partner_id": order_data["partner_id"],
            "origin": _("Point of Sale %s") % (session.name),
            "client_order_ref": order_data["name"],
            "user_id": order_data["user_id"],
            "pricelist_id": order_data["pricelist_id"],
            "fiscal_position_id": order_data["fiscal_position_id"],
        }

    @api.model
    def create_order_from_pos(self, order_data, action):
        invoice_lines = []
        SaleOrderLine = self.env["sale.order.line"]

        # Create Draft Sale order
        order_vals = self._prepare_from_pos(order_data)
        sale_order = self.create(order_vals.copy())
        sale_order.onchange_partner_id()
        # we rewrite data, because onchange could alter some
        # custom data (like pricelist)
        sale_order.write(order_vals)

        # create Sale order lines
        for order_line_data in order_data["lines"]:
            invoice_vals = {
                'name': order_line_data[2]['full_product_name'],
                'price_unit': order_line_data[2]['price_unit'],
                'quantity': order_line_data[2]['qty'],
                'product_id': order_line_data[2]['product_id'],
                'tax_ids': order_line_data[2]['tax_ids'],
            }
            # Create Sale order lines
            order_line_vals = SaleOrderLine._prepare_from_pos(
                sale_order, order_line_data[2])
            sale_order_line = SaleOrderLine.create(
                order_line_vals.copy())
            sale_order_line.product_id_change()
            # we rewrite data, because onchange could alter some
            # data (like quantity, or price)
            sale_order_line.write(order_line_vals)
        invoice_lines.append((0, 0, invoice_vals))

        # Confirm Sale Order
        if action in ["confirmed", "delivered"]:
            sale_order.action_confirm()

        # mark picking as delivered
        if action == "delivered":
            # Mark all moves are delivered
            for move in sale_order.mapped(
                    "picking_ids.move_ids_without_package"):
                move.quantity_done = move.product_uom_qty
            sale_order.mapped("picking_ids").button_validate()
        #Create invoice based on order
        PaymentMethods = self.env["payment.methods"]
        paymentmethod = PaymentMethods.search([('name','=','Efectivo')])
        _logger.info(paymentmethod.id)
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'ref' : sale_order.name,
            'invoice_user_id': order_vals['user_id'],
            'partner_id' : order_vals['partner_id'],
            'payment_methods_id' : paymentmethod.id,
            'invoice_line_ids': invoice_lines
        })
        invoice.action_post()

        return {
            "sale_order_id": sale_order.id,
        }
