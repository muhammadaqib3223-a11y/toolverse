from flask_babel import lazy_gettext as _l

from app.blueprints.tools.cv_generator.saved_cvs import MAX_SAVED_CVS
from app.blueprints.tools.cv_generator.services import MAX_EDUCATION, MAX_EXPERIENCE, MAX_SKILLS

ERROR_MESSAGES = {
    "invalid_data": _l("Something in the form is not right. Please check it and try again."),
    "name_required": _l("Please type your full name."),
    "email_invalid": _l("Please type a valid email address."),
    "website_invalid": _l("Please type a website like example.com or https://example.com."),
    "too_long": _l("This is too long. Please shorten it."),
    "too_many_experience": _l("You can add up to %(max)s jobs.", max=MAX_EXPERIENCE),
    "too_many_education": _l("You can add up to %(max)s education entries.", max=MAX_EDUCATION),
    "too_many_skills": _l("You can add up to %(max)s skills.", max=MAX_SKILLS),
    "template_invalid": _l("Please choose a template."),
    "accent_invalid": _l("Please choose a colour."),
    "title_too_long": _l("The CV name is too long (120 characters max)."),
    "login_required": _l("Please log in to save your CVs."),
    "not_found": _l("That CV no longer exists."),
    "cv_limit": _l("You can keep up to %(max)s CVs. Delete one to add a new one.", max=MAX_SAVED_CVS),
    "unavailable": _l("Your CVs can't be reached right now. Please try again in a moment."),
    "section_invalid": _l("Please choose what the AI should improve."),
    "nothing_to_improve": _l("Write a few words here first, then the AI can make them sound professional."),
    "limit_guest": _l("You have used your free AI help for today. Log in or sign up free to get more."),
    "limit_user": _l("You have used all your AI help for today. Come back tomorrow."),
    "site_limit": _l("The AI is very busy today. Please try again tomorrow."),
    "ai_quota": _l("The AI is busy right now. Please try again in a minute."),
    "ai_blocked": _l("The AI couldn't work on this text. Please change it a little and try again."),
    "ai_unavailable": _l("The AI isn't available right now. Please try again in a moment."),
    "language_invalid": _l("Please choose the CV language."),
    "too_large": _l("Your CV is too long to turn into a PDF. Please shorten it."),
    "pdf_failed": _l("We couldn't make your PDF. Please try again in a moment."),
    "unknown": _l("Something went wrong. Please try again."),
}


def error_message(error):
    return ERROR_MESSAGES.get(error.code, ERROR_MESSAGES["unknown"])
