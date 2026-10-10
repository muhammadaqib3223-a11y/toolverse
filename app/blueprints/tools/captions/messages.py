from flask_babel import lazy_gettext as _l

ERROR_MESSAGES = {
    "login_required": _l("Please log in to use this."),
    "not_found": _l("That caption set no longer exists."),
    "topic_required": _l("Please type a topic."),
    "topic_too_long": _l("The topic is too long (500 characters max)."),
    "platform_invalid": _l("Please choose Instagram or LinkedIn."),
    "limit_guest": _l("You have used your free tries for today. Log in or sign up free to get more."),
    "limit_user": _l("You have used all your captions for today. Come back tomorrow."),
    "site_limit": _l("The Caption Generator is very busy today. Please try again tomorrow."),
    "ai_quota": _l("The AI is busy right now. Please try again in a minute."),
    "ai_blocked": _l("The AI couldn't write captions for this topic. Please try a different topic."),
    "ai_unavailable": _l("The AI isn't available right now. Please try again in a moment."),
    "unavailable": _l("Captions aren't available right now. Please try again in a moment."),
    "unknown": _l("Something went wrong. Please try again."),
}


def error_message(error):
    return ERROR_MESSAGES.get(error.code, ERROR_MESSAGES["unknown"])
