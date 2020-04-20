# -*- coding: utf-8 -*-
# @Time: 2020/4/17
# @File: generate_site

'''
生成nginx配置文件
'''

import paramiko
from django.conf import settings
from io import StringIO
import os
from publish import tools
import socket
from publish.tools import Config, record_log


class GenerateSiteConf(object):

    logger = tools.record_log()

    def __init__(self, cr_file_path, domain_name, url_path, index_page='index.html'):
        self.cr_file_path = cr_file_path
        self.domain_name = domain_name
        self.url_path = url_path
        self.html_dir = domain_name.rsplit('.', 1)[0]
        self.config_data = {
            'html_dir': self.html_dir,
            'index_page': index_page,
            'domain_name': domain_name,
            'log_prefix': domain_name.rsplit('.', 1)[0].replace('.', '_'),
            'domain_suffix': '.'.join(domain_name.split('.')[1:]),
        }
        self.config_name_path = settings.HTTP_SERVER_HOME_DIR + '/' + domain_name

    def login_auth(self, host, private_key, user, port):
        pkey = paramiko.RSAKey.from_private_key_file(os.path.join(settings.PRIVATE_KEY_DIR, private_key))
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.ssh.connect(hostname=host, port=port, username=user, pkey=pkey)
            return True
        except Exception as e:
            self.logger.error('ssh connect {},{},{},{} failed: {}'.format(host, private_key, user, port, str(e)))
            return False

    def determine_conf_file(self):
        stdin, stdout, stderr = self.ssh.exec_command('ls {}'.format(self.config_name_path))
        error = stderr.read()
        if error:  # 没有配置文件
            self.translate_file()
        else:
            self.logger.warn('config file already exists. [ {} ]'.format(self.config_name_path))

    def translate_file(self):
        sftp = self.ssh.open_sftp()
        sftp.chdir(settings.HTTP_SERVER_HOME_DIR)  # nginx配置文件
        print(self.gen_site_conf(), self.domain_name)
        sftp.putfo(self.gen_site_conf(), self.domain_name)
        self.logger.info("create nginx config file: {}".format(self.domain_name))
        for root, dirs, files in os.walk(self.cr_file_path):
            if files:
                for f in files:
                    target_related_dir = root.split(self.cr_file_path)[-1].lstrip(os.sep)
                    target_dir_path = '{}/{}/{}/{}'.format(settings.NGINX_HTML_DIR, self.html_dir, self.url_path,
                                                           target_related_dir).rstrip('/')
                    if target_dir_path:
                        stdin, stdout, stderr = self.ssh.exec_command("mkdir -p {}".format(target_dir_path))
                        if not stderr.read():
                            source_f = os.path.join(root, f)
                            target_f = '{}/{}'.format(target_dir_path, f)
                            sftp.put(source_f, target_f)
        self.logger.info("copy html file to {}/{}/{}".format(settings.NGINX_HTML_DIR, self.html_dir, self.url_path))
        self.ssh.exec_command('/usr/bin/env nginx -s reload')
        self.logger.info("reload nginx daemon")

    def gen_site_conf(self):
        result = settings.SITE_CONF_TEMPLATE.format(**self.config_data)
        result = 'server {' + result + '}'
        f = StringIO(result)
        return f

    def resolve_address(self):
        try:
            return socket.gethostbyname(self.domain_name)
        except Exception:
            return False

    @staticmethod
    def read_config(host):
        config = Config()
        return config.get_data(host)


    def run(self):
        server_address = self.resolve_address()
        if not server_address:
            return '无法解析域名'
        server_config = self.read_config(server_address)
        if not server_config['status']:
            message = '读取服务器登陆信息失败: {}'.format(server_address)
            self.logger.error(message)
            return message
        res = self.login_auth(server_address, server_config['private_key'], server_config['user'], server_config['port'])
        if not res:
            return res
        # self.determine_conf_file()
        self.translate_file()
        return True