from flask_babel import lazy_gettext as _l

ERROR_MESSAGES = {
    "login_required": _l("Please log in to use this."),
    "not_found": _l("That expense no longer exists."),
    "amount_required": _l("Please enter an amount."),
    "amount_invalid": _l("The amount must be a positive number."),
    "description_required": _l("Please describe the expense."),
    "description_too_long": _l("The description is too long (200 characters max)."),
    "date_invalid": _l("Please enter a valid date."),
    "unavailable": _l("Expenses aren't available right now. Please try again in a moment."),
    "unknown": _l("Something went wrong. Please try again."),
}


def error_message(error):
    return ERROR_MESSAGES.get(error.code, ERROR_MESSAGES["unknown"])
