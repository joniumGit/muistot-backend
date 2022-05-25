ROOT = ""
AUTH_PREFIX = "/auth"

PROJECTS = ROOT + "/projects"
PROJECT = PROJECTS + "/{}"
SITES = PROJECT + "/sites"
SITE = SITES + "/{}"
MEMORIES = SITE + "/memories"
MEMORY = MEMORIES + "/{}"
COMMENTS = MEMORY + "/comments"
COMMENT = COMMENTS + "/{}"

IMAGE = "/images/{}"
ADMINS = PROJECT + "/admins"

PUBLISH = "/admin/publish"
REPORT = "/report"
ENTRY = "/"

STATUS = ROOT + AUTH_PREFIX + "/status"
LOGIN = ROOT + AUTH_PREFIX + "/password"
EMAIL_LOGIN = ROOT + AUTH_PREFIX + "/email"
EMAIL_EXCHANGE = ROOT + AUTH_PREFIX + "/email/exchange"
OAUTH_BASE = ROOT + AUTH_PREFIX + "/oauth"
REGISTER = ROOT + AUTH_PREFIX + "/register"
CONFIRM = ROOT + AUTH_PREFIX + "/confirm"

PUBLISH_PROJECT = PROJECT + "/publish?publish={}"
PUBLISH_SITE = SITE + "/publish?publish={}"
PUBLISH_MEMORY = MEMORY + "/publish?publish={}"
PUBLISH_COMMENT = COMMENT + "/publish?publish={}"
