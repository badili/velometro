
from __future__ import unicode_literals

import frappe
from frappe import _, throw
from erpnext.accounts.doctype.pricing_rule.pricing_rule import get_pricing_rule_for_item, get_pricing_rules, filter_pricing_rules, apply_pricing_rule
from frappe.utils import flt
import json

@frappe.whitelist()
def add_pricing_rules(mquotation, method=None):
	"""This function adds all the items to pricing rules"""
	frappe.msgprint(_("Adding Pricing Rules"))
	quotation = frappe.get_doc("Supplier Quotation",mquotation)

	# Loop through all of the items in the price list
	for item_doc in quotation.items:
		#  check to see if there are any pricing rules that fall into the specified quantity/supplier
		#frappe.msgprint(_("Checking pricing rules of {0} for previous prices".format(item_doc.item_code)))
		item = frappe.get_doc("Item",item_doc.item_code)
		args = {
			"doctype": item_doc.doctype,
			"parent_type": item_doc.parenttype,
			"name": item_doc.name,
			"item_code": item_doc.item_code,
			"transaction_type": "buying",
			"supplier": quotation.supplier,
			"qty": item_doc.qty,
			"price_list": quotation.buying_price_list,
			"company": quotation.company
		}

		args = frappe._dict(args)

		pr_result = get_pricing_rule_for_item(args)

		if not pr_result.pricing_rule:
			frappe.msgprint(_("There are no pricing rules for this item"))
			pr_title = item_doc.item_code + "-" + quotation.supplier + "-" + str(item_doc.qty)
			new_rule = frappe.get_doc({"doctype":"Pricing Rule", "min_qty": item_doc.qty, "apply_on": "Item Code", "item_code": item_doc.item_code, "priority": 1, "buying": "1", "applicable_for": "Supplier", "company": quotation.company, "price_or_discount": "Price", "price": item_doc.rate, "supplier": quotation.supplier, "for_price_list" : quotation.buying_price_list, "title": pr_title, "from_supplier_quotation": quotation.name })
			new_rule.insert()

		else:
			frappe.msgprint(_("Pricing Rule {0} applies for this item".format(pr_result.pricing_rule)))

			# Check to see if the pricing rule matches quantity min exactly
			pricing_rule = frappe.get_doc("Pricing Rule", pr_result.pricing_rule)
			if item_doc.qty == pricing_rule.min_qty:
				# This pricing rule rate just needs to be changed
				frappe.msgprint(_("Updating Pricing Rule"))
				frappe.set_value("Pricing Rule", pricing_rule.name, "price",item_doc.rate)

			else:
				frappe.msgprint(_("Creating new rule and incrementing priority"))
				# This rule is lower in qty than the current rule. We need to add a new pricing rule and update the priorities for each of the higher quantity pricing rules
				pr_title = item_doc.item_code + "-" + quotation.supplier + "-" + str(item_doc.qty)
				new_rule = frappe.get_doc({"doctype":"Pricing Rule", "min_qty": item_doc.qty, "apply_on": "Item Code", "item_code": item_doc.item_code, "priority": pricing_rule.priority, "buying": "1", "applicable_for": "Supplier", "company": quotation.company, "price_or_discount": "Price", "price": item_doc.rate, "supplier": quotation.supplier, "for_price_list" : quotation.buying_price_list, "title": pr_title, "from_supplier_quotation": quotation.name })
				new_rule.insert()

				# Run through each of the higher quantity pricing rules and increase their priority by one
				unfiltered_rules = get_pricing_rules(args)
				pricing_rules = filter(lambda x: (flt(item_doc.qty)<=flt(x.min_qty)), unfiltered_rules)
				for pr in pricing_rules:
					if pr.priority == '':
						continue
					frappe.set_value("Pricing Rule", pr.name, "priority",str(int(pr.priority) + 1))
					#frappe.msgprint(_("Incorporating new Pricing rule between others".format(pr.name, pr.priority)))


@frappe.whitelist()
def copy_pricing_rule_from_previous_revision(base_item_code, current_rev):
	"""This function adds all the items to pricing rules"""
	new_code = str(base_item_code) + "_" + str(int(current_rev))
	args = {
		"item_code": str(base_item_code) + "_" + str(int(current_rev)-1),
		"transaction_type": "buying"
	}


	args = frappe._dict(args)
	frappe.msgprint(_("Copying Pricing Rules for " + args.item_code))
	pr_result = get_pricing_rules(args)


	pr_result =  frappe.db.sql("""SELECT * FROM `tabPricing Rule` WHERE item_code=%(item_code)s ORDER by priority desc, name desc""", args , as_dict=1)

	for rule in pr_result:
		frappe.msgprint("Copying rule: " + str(rule.name))
		pr_title = new_code + "-" + rule.supplier + "-" + str(rule.min_qty)
		new_rule = frappe.get_doc({"doctype":"Pricing Rule", "min_qty": rule.min_qty, "apply_on": rule.apply_on, "item_code": new_code, "priority": rule.priority, "buying": rule.buying, "applicable_for": rule.applicable_for, "company": rule.company, "price_or_discount": rule.price_or_discount, "price": rule.price, "supplier": rule.supplier, "for_price_list" : rule.for_price_list, "title": pr_title, "from_supplier_quotation": rule.from_supplier_quotation })
		new_rule.insert()

@frappe.whitelist()
def fetch_unquoted_items(mquotation, method=None):
	"""This function gets all the unquoted items. It compares the submitted supplier quotation with the sent RFQ"""
	frappe.msgprint(_("Fetching the RFQ for this supplier quotation"))
	quotation = frappe.get_doc("Supplier Quotation", mquotation)
	rfq = frappe.get_doc("Request for Quotation", quotation.request_for_quotation)

	# Loop through all of the items in the price list
	unquoted_items = {}
	all_rfq_items = {}
	all_quoted_items = {}

	# first process the rfq items to ensure we are only dealing with a unique list
	for rfq_item in rfq.items:
		# check if there is a case of duplicate items in the RFQ. If its there, just add the numbers
		if rfq_item.item_code not in all_rfq_items:
			all_rfq_items[rfq_item.item_code] = rfq_item
		else:
			frappe.msgprint("Duplicate item '%s' in the RFQ %s. Adding the number items" %s (rfq_item.item_code, quotation.request_for_quotation))
			all_rfq_items[rfq_item.item_code].qty = rfq_item.qty + all_rfq_items[rfq_item.item_code].qty

	# process the quoted items to ensure that we are only dealing with unique items too
	for quoted_item in quotation.items:
		if quoted_item.item_code not in all_quoted_items:
			all_quoted_items[quoted_item.item_code] = quoted_item
		else:
			frappe.msgprint("Duplicate item '%s' in the Supplier Quotation %s. Adding the number items" %s (quoted_item.item_code, mquotation))
			all_quoted_items[quoted_item.item_code].qty = quoted_item.qty + all_quoted_items[quoted_item.item_code].qty

		for rfq_item_code, rfq_item in all_rfq_items.iteritems():
			is_fully_quoted = False
			is_added_to_unquoted = False
			for quoted_item_code, quoted_item in all_quoted_items.iteritems():
				if rfq_item_code == quoted_item_code:
					if rfq_item.qty != quoted_item.qty:
						# we have a discrepancy in the number of items quoted, so add the difference to the unquoted items
						rfq_item.qty = rfq_item.qty - quoted_item.qty
						unquoted_items[rfq_item_code] = rfq_item
						is_added_to_unquoted = True
					else:
						# all has been quoted fully
						is_fully_quoted = True

			# now check if our item is fully quoted, if not add it to the unquoted items
			if is_fully_quoted == False and is_added_to_unquoted == False:
				unquoted_items[rfq_item_code] = rfq_item

	frappe.msgprint("We have %d unquoted items" % len(unquoted_items))


