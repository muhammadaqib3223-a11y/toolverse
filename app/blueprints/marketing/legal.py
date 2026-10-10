"""Text of the Privacy Policy (/privacy) and Terms of Service (/terms). Every string is translatable.

Each page is a list of blocks: headings (h2/h3), paragraphs (p), lists (ul/ol), a highlighted
note, or a table. In the text, %(email)s becomes the contact email link and %(cookie)s the
name of our cookie (see templates/marketing/legal.html).

These pages describe what the code really does. When the code changes (a new cookie, a new
service, a "Delete account" button...), update this file and the "updated" date.
"""
from dataclasses import dataclass
from datetime import date

from flask_babel import lazy_gettext as _l


@dataclass(frozen=True)
class Block:
    kind: str           # "h2", "h3", "p", "ul", "ol", "note" or "table"
    text: str = None    # h2, h3, p, note
    items: tuple = ()   # ul / ol: one text per item; table: one (cell, cell) pair per row
    header: tuple = ()  # table only


@dataclass(frozen=True)
class LegalPage:
    endpoint: str
    title: str
    meta_description: str
    updated: date
    blocks: tuple


def _h2(text):
    return Block("h2", text)


def _h3(text):
    return Block("h3", text)


def _p(text):
    return Block("p", text)


def _ul(*items):
    return Block("ul", items=items)


def _ol(*items):
    return Block("ol", items=items)


PRIVACY = LegalPage(
    endpoint="marketing.privacy",
    title=_l("Privacy Policy"),
    meta_description=_l("How Toolverse collects, uses and protects your data, in plain words: "
                        "what we save, the AI we use, cookies, and how to delete your account."),
    updated=date(2026, 10, 10),
    blocks=(
        _h2(_l("The short version")),
        _ul(
            _l("We only collect what we need to run the five tools."),
            _l("Your CVs, notes and expenses are private to your account. Only you can see them."),
            _l("If you check a CV as a guest (without logging in), the file is checked and then thrown away. "
               "It is never saved."),
            _l("We do not sell your data, we do not show ads, and we do not use tracking or advertising cookies."),
            _l("To check CVs and write captions, we send text to Google's Gemini AI. "
               "Please read the \"AI\" section below."),
            _l("You can ask us to delete your account and all your data at any time."),
        ),

        _h2(_l("Who we are")),
        _p(_l("Toolverse is a free web app with five tools: CV Checker, CV Generator, Captions, Notes and "
              "Expenses. It is run by a small independent team. You can reach us at %(email)s.")),

        _h2(_l("What we collect")),
        _h3(_l("Your account")),
        _ul(
            _l("Your email address and your password. Your password is stored in scrambled (hashed) form by "
               "our login provider, Supabase. Nobody at Toolverse can read it."),
            _l("If you log in with Google: your name, email address and profile picture link from Google. "
               "We do not get your Google password, and we cannot see your Gmail, Drive or anything else "
               "in your Google account."),
        ),
        _h3(_l("What you put into the tools")),
        _ul(
            _l("CV Checker: the PDF you upload, the text inside it, and your score and tips."),
            _l("CV Generator: the details you type in (name, contact details, summary, work experience, "
               "education, skills) and the CVs you create."),
            _l("Captions: the topic you type and the captions you get."),
            _l("Notes: your notes."),
            _l("Expenses: the amounts and descriptions you enter, and your currency setting."),
        ),
        _h3(_l("When you use the tools as a guest (without an account)")),
        _ul(
            _l("To keep the free AI tries fair, we count how many tries each internet address (IP address) "
               "has used. We store this count, not your content."),
            _l("Guest notes and expenses are saved only in your own browser, not on our servers. When you log "
               "in, you can move them into your account."),
            _l("A CV checked as a guest is never saved."),
        ),
        _h3(_l("Technical information")),
        _p(_l("Like almost every website, our hosting (Vercel) and our database (Supabase) keep short-term "
              "technical logs: IP address, browser type, pages visited, time, and errors. We use these only "
              "to keep the site working and safe.")),

        _h2(_l("How we use your information")),
        _ul(
            _l("To run the tools and save your work in your account."),
            _l("To log you in and keep your account safe."),
            _l("To send you emails you need: confirming your email and resetting your password. "
               "We do not send marketing emails."),
            _l("To keep the daily limits fair and stop abuse."),
            _l("To fix errors."),
        ),

        _h2(_l("AI (Google Gemini)")),
        _ul(
            _l("When you check a CV, the text of your CV is sent to Google's Gemini AI so it can give a score "
               "and tips."),
            _l("When you write captions, your topic is sent to Gemini."),
            _l("When you ask for AI help in the CV Generator, the details you typed for that part are sent "
               "to Gemini."),
        ),
        Block("note", _l("We use the free version of Gemini. Under Google's terms for the free version, Google "
                         "may use what we send to improve its products, and people at Google may read it. "
                         "Because of this, please do not put very sensitive information (for example ID card "
                         "numbers or bank details) into a CV you check with AI.")),
        _p(_l("AI can make mistakes. Always read the results yourself.")),

        _h2(_l("Where your data is stored")),
        _ul(
            _l("Your account and data are stored with Supabase (database, file storage and login). Every table "
               "is protected with Row Level Security, so each account can only read its own data."),
            _l("The website runs on Vercel."),
            _l("These companies may store data on servers outside Pakistan."),
        ),

        _h2(_l("Who we share it with")),
        _p(_l("We only share data with the services we need to run Toolverse:")),
        Block(
            "table",
            header=(_l("Service"), _l("What for")),
            items=(
                ("Supabase", _l("Login, database, CV files, sending account emails")),
                ("Vercel", _l("Hosting the website")),
                ("Google", _l("\"Continue with Google\" login, Gemini AI, and the website's fonts")),
            ),
        ),
        _p(_l("We do not sell your data and we do not share it with advertisers. We only give data to anyone "
              "else if the law requires it.")),

        _h2(_l("Cookies")),
        _ul(
            _l("We use one cookie, called %(cookie)s. It keeps you logged in and protects our forms against "
               "misuse. It is needed for the site to work. It lasts up to 30 days and is renewed each time "
               "you visit."),
            _l("We do not use analytics, advertising or tracking cookies."),
            _l("Guest notes and expenses use your browser's own storage (not a cookie), and stay on your device."),
            _l("Our fonts are loaded from Google Fonts, so your browser connects to Google when a page opens."),
        ),

        _h2(_l("How long we keep your data")),
        _ul(
            _l("Your account data is kept while your account exists."),
            _l("If you delete something (for example a note or a saved CV), it is deleted right away and "
               "cannot be recovered."),
            _l("If you ask us to delete your account, we delete your account and all its data within 30 days. "
               "Copies may stay in our providers' backups for a short time after that, and are then removed."),
            _l("Guest CVs are never stored. Guest try counts are kept only as long as needed for the daily "
               "limits."),
        ),

        _h2(_l("Deleting your account")),
        _p(_l("There is no \"Delete account\" button yet. Until there is one:")),
        _ol(
            _l("Send an email to %(email)s from the email address of your account."),
            _l("Write \"Delete my account\" in the subject."),
            _l("We will delete your account and all your data (CVs, notes, expenses, captions) within 30 days, "
               "and reply to confirm."),
        ),
        _p(_l("You can also delete your notes, expenses and CVs yourself at any time inside the tools.")),

        _h2(_l("Your choices")),
        _ul(
            _l("You can see, edit and delete your own data inside the tools."),
            _l("You can ask us for a copy of your data, or ask us to correct or delete it, by emailing us."),
            _l("You can clear guest data by clearing your browser's site data."),
        ),

        _h2(_l("Keeping your data safe")),
        _p(_l("We use HTTPS on every page, private storage for CVs, and Row Level Security on every table. "
              "No website can promise perfect security, but we work hard to protect your data. If something goes "
              "wrong that affects your data, we will tell you.")),

        _h2(_l("Age limit")),
        _p(_l("Toolverse is only for people aged 18 or older. If you think someone under 18 has made an "
              "account, email us and we will delete it.")),

        _h2(_l("Changes to this policy")),
        _p(_l("If we change this policy, we will update the date at the top. If the change is important, "
              "we will also show a notice on the site.")),

        _h2(_l("Contact")),
        _p(_l("Questions about your privacy? Email %(email)s.")),
    ),
)


TERMS = LegalPage(
    endpoint="marketing.terms",
    title=_l("Terms of Service"),
    meta_description=_l("The simple rules for using Toolverse: free tools, fair daily limits, your content "
                        "stays yours, and AI can make mistakes."),
    updated=date(2026, 10, 10),
    blocks=(
        _h2(_l("1. Agreeing to these terms")),
        _p(_l("By using Toolverse, with or without an account, you agree to these terms. If you do not agree, "
              "please do not use Toolverse.")),

        _h2(_l("2. What Toolverse is")),
        _p(_l("Toolverse is a free web app with five tools: CV Checker, CV Generator, Captions, Notes and "
              "Expenses. Some tools may still be \"coming soon\". We may add, change or remove features over "
              "time.")),

        _h2(_l("3. Free to use")),
        _ul(
            _l("Toolverse is free. There are no paid plans and we never ask for a credit card."),
            _l("AI tools have a fair daily limit, and guests get a small number of free tries, so the service "
               "can stay free for everyone. We may change these limits."),
            _l("If we ever offer paid features, we will tell you first. We will never charge you without your "
               "clear permission."),
        ),

        _h2(_l("4. Your account")),
        _ul(
            _l("You must be at least 18 years old."),
            _l("Use a real email address that belongs to you."),
            _l("Keep your password safe. You are responsible for what happens in your account."),
            _l("One account is for one person."),
        ),

        _h2(_l("5. Your content")),
        _ul(
            _l("What you create or upload (CVs, notes, expenses, captions) belongs to you."),
            _l("You give us permission only to store and process it so the tools can work for you, including "
               "sending it to Gemini AI where needed (see the Privacy Policy)."),
            _l("Only upload content you have the right to use. Do not upload other people's personal data "
               "without their permission."),
        ),

        _h2(_l("6. AI results")),
        _ul(
            _l("The CV score, tips, captions and writing help come from AI. AI can make mistakes. "
               "Check everything before you use it."),
            _l("The CV Checker gives a score and tips. It does not rewrite your CV, and it cannot promise you "
               "a job or an interview."),
            _l("Toolverse never posts on social media for you and does not connect to your social media "
               "accounts. You choose what to post."),
        ),

        _h2(_l("7. Fair use")),
        _p(_l("Please do not:")),
        _ul(
            _l("break the law, or use Toolverse to harm, cheat or harass anyone;"),
            _l("try to get around the daily limits, for example with many accounts or automated scripts;"),
            _l("try to break into Toolverse, other people's accounts, or our providers' systems;"),
            _l("upload viruses or harmful files;"),
            _l("use Toolverse to send spam."),
        ),

        _h2(_l("8. Availability and backups")),
        _p(_l("We try to keep Toolverse working well, but because it is a free service we cannot promise it "
              "will always be available or free of errors. Toolverse is provided \"as is\". Please keep your "
              "own copy of important files, such as your final CV PDF.")),

        _h2(_l("9. Limits on our responsibility")),
        _p(_l("As far as the law allows, Toolverse is not responsible for indirect losses, such as a missed "
              "job opportunity or lost data, that come from using or not being able to use the service.")),

        _h2(_l("10. Ending your use")),
        _ul(
            _l("You can stop using Toolverse at any time and ask us to delete your account (see the Privacy "
               "Policy)."),
            _l("We may suspend or close an account that breaks these terms. Where possible, we will tell "
               "you why."),
        ),

        _h2(_l("11. Changes to these terms")),
        _p(_l("If we change these terms, we will update the date at the top. If the change is important, we "
              "will show a notice on the site. If you keep using Toolverse after a change, it means you accept "
              "the new terms.")),

        _h2(_l("12. Law")),
        _p(_l("These terms follow the laws of Pakistan.")),

        _h2(_l("13. Contact")),
        _p(_l("Questions? Email %(email)s.")),
    ),
)

PAGES = (PRIVACY, TERMS)
