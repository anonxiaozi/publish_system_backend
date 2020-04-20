# -*- coding: utf-8 -*-
# @Time: 2020/4/17
# @File: operate_gitlab

import gitlab
import os
import tarfile
from io import BytesIO
from django.conf import settings
import shutil


class OperateGit(object):

    def __init__(self, gitlab_url, private_token):
        self.gl = gitlab.Gitlab(gitlab_url, private_token=private_token)
        self.gl.auth()

    def pull_object(self):
        temp = self.gl.projects.get(settings.TEMPLATE_PROJECT_ID)
        tgz = temp.repository_archive(streamed=False)
        self.unarchive(tgz)

    def unarchive(self, git_data, sign='html_template'):
        self.delete_file()
        f = BytesIO(git_data)
        with tarfile.open(mode='r', fileobj=f) as zf:
            member = zf.members[0].name
            if not member.startswith(sign):
                for m in zf.members:
                    if m.name.startswith(sign):
                        member = m.name
                        break
            zf.extractall(settings.TMP_GIT_DOWN_DIR)
        f.close()
        with tarfile.open(settings.TMP_GIT_SAVE_NAME, 'w:gz') as f:
            for item in os.listdir(os.path.join(settings.TMP_GIT_DOWN_DIR, member)):
                f.add(name=settings.TMP_GIT_DOWN_DIR + os.sep + member + os.sep + item, arcname=item, recursive=True)
        shutil.rmtree(settings.CR_TEMPLATE_PATH, ignore_errors=True)
        with tarfile.open(settings.TMP_GIT_SAVE_NAME, 'r') as f:
            f.extractall(settings.CR_TEMPLATE_PATH)
        self.delete_file()

    @staticmethod
    def delete_file():
        shutil.rmtree(settings.TMP_GIT_DOWN_DIR, ignore_errors=True)
        if os.path.exists(settings.TMP_GIT_SAVE_NAME):
            os.remove(settings.TMP_GIT_SAVE_NAME)