"""Flask extension objects, created once and bound to the app in create_app()."""
from flask_babel import Babel
from flask_wtf.csrf import CSRFProtect

babel = Babel()
csrf = CSRFProtect()
