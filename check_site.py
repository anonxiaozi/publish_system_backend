# -*- coding: utf-8 -*-
# @Time: 2020/4/17
# @File: check_site

"""
监控网站是否正常运行
"""

from urllib import request
import json
import copy
import requests
import datetime
import os


class CheckURL(object):

    def __init__(self, access_token='', key='', timeout=5):
        self.domain_file = os.path.join(os.path.dirname(__file__), 'domain_list.json')
        self.domain_dict = self.get_domain()
        self.result = copy.deepcopy(self.domain_dict)
        self.timeout = timeout
        self.access_token = access_token
        self.key = key

    def get_domain(self):
        try:
            with open(self.domain_file, 'r', encoding='utf-8') as f:
                self.domain_dict = json.load(f)
            return self.domain_dict
        except Exception as e:
            self.domain_dict = {}

    def check_url(self, url):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36',
        }
        req = request.Request(url, headers=headers, method='GET')
        try:
            request.urlopen(req, timeout=self.timeout)
            self.result[url]['status'] = 200
            self.result[url]['count'] = 0
        except Exception as e:
            self.result[url]['status'] = str(e)
            self.modify_count(url, str(e))

    def modify_count(self, url, error):
        content = '时间: {}\nURL: {} 访问失败'.format(datetime.datetime.now(), url)
        if self.result[url]['count'] >= 2:
            del(self.result[url])
            content += '  [移除监测]'
        elif self.result[url]['status'] != 200:    # 上次访问的结果是失败的
            self.result[url]['count'] += 1
            content += '\n访问结果: {}'.format(error)
        content += '\n关键词: {}'.format(self.key)
        self.send_talk(content)

    def record(self, data):
        with open(self.domain_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    def send_talk(self, content):
        url = 'https://oapi.dingtalk.com/robot/send?access_token={}'.format(self.access_token)
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "msgtype": "text",
            "text": {
                "content": content,
            }
        }
        send_data = json.dumps(data)
        requests.post(url, data=send_data, headers=headers)

    @property
    def url_dict(self):
        return self.domain_dict

    @url_dict.setter
    def url_dict(self, *args):
        """
        修改url检测数据，传递参数必须是一个字典，必须要有两个key: url和sign
        例如添加对abc.com的监控：{'url': 'http://abc.com', 'sign': True}
        """
        if args:
            for arg in args[0]:
                if not self.domain_dict:
                    self.domain_dict = {}
                if arg['sign']:
                    if arg['url'] not in self.domain_dict:
                        self.domain_dict[arg['url']] = {
                            'status': 200,
                            'count': 0,
                        }
                else:
                    if arg['url'] in self.domain_dict:
                        del(self.domain_dict[arg['url']])

    def run(self):
        for url in self.domain_dict:
            self.check_url(url)
        else:
            self.record(self.result)


if __name__ == '__main__':
    access_token = ''
    key = 'check_url'
    check = CheckURL(access_token, key)
    check.run()