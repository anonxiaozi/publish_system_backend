from django.conf import settings
from publish import tools
import os

tools.check_dir(
    'publish' + os.sep + 'logs',
    settings.CR_TEMPLATE_PATH,
    settings.TMP_GIT_DOWN_DIR,
    settings.PRIVATE_KEY_DIR,
)
