# -*- coding: utf-8 -*-
# @Time: 2020/4/17
# @File: tools

import os
import logging
import pymongo
from bson import ObjectId
from django.conf import settings
import requests
import json
from datetime import datetime
import configparser


def check_dir(*dir_path):
    for path in dir_path:
        if not os.path.exists(path):
            os.makedirs(path)


def check_file(file_path):
    if not os.path.exists(file_path):
        return False
    else:
        return True


class ConnectDB(object):

    def __init__(self, **kwargs):
        self.args = kwargs["args"]
        self.conn = pymongo.MongoClient(self.args["host"], self.args["port"])
        self.db = self.conn[self.args['db']]
        self.table = self.db[self.args['table']]
        self.dist_table = self.db[self.args['dist_history']]
        self.guider_history = self.db[self.args['guider_history']]
        self.cr_history = self.db[self.args['cr_history']]
        self.cr_tags = self.db[self.args['cr_tags']]
        self.creativeData = self.db[self.args['creativeData']]
        self.logger = record_log()

    def insert_record(self, record):
        self.table.insert(record)

    def record_cr_online(self, cr, status):
        # self.cr_history.insert({'cr': cr, 'online': status, 'time': datetime.now(pytz.timezone("Asia/Shanghai"))})
        self.cr_history.insert({'cr': cr, 'online': status, 'time': datetime.now()})
        if not self.cr_tags.find_one({'_id': cr}):
            self.cr_tags.insert({'_id': cr, 'tags': [], 'area': '', 'route': '', 'online': status})
        else:
            self.cr_tags.find_one_and_update(
                {'_id': cr},
                {'$set': {'online': status, '_id': cr}},
                upsert=True
            )

    def replace_monit_from_cr(self, cr, status):
        self.dist_table.update_many(
            {'cr': cr},
            {'$set': {'monitor': status}},
            upsert=True
        )

    def get_cr_related_link(self, cr):
        cursor = self.dist_table.aggregate([
            {
                '$match': {
                    'cr': cr
                }
            }, {
                '$group': {
                    '_id': '$link'
                }
            }
        ])
        data = [x for x in cursor]
        if data:
            return [x['_id'] for x in data]
        else:
            return []

    def get_signle_cr_online_status(self, cr):
        aggregate_instruction = [
            {
                '$sort': {
                    'time': -1
                }
            }, {
                '$group': {
                    '_id': '$cr',
                    'online': {
                        '$first': '$online'
                    }
                }
            }
        ]
        cursor = self.cr_history.aggregate(aggregate_instruction)
        result = [x for x in cursor][0]
        return result['online']

    def get_cr_list_online_status(self, cr_list):
        aggregate_instruction = [
            {
                '$sort': {
                    'time': -1
                }
            }, {
                '$group': {
                    '_id': '$cr',
                    'online': {
                        '$first': '$online'
                    }
                }
            }
        ]
        facet_instruction = {'$facet': {}}
        for cr in cr_list:
            facet_instruction['$facet'][cr] = [{
                '$match': {
                    '_id': cr,
                    'online': True
                }
            }]
        aggregate_instruction.append(facet_instruction)
        cursor = self.cr_history.aggregate(aggregate_instruction)
        result = {}
        for item in cursor:
            for cr_name, online_data in item.items():
                result[cr_name] = True if online_data else False
        return result

    def get_cr_list_online_status_2(self, cr_list):
        aggregate_instruction = [
            {
                '$sort': {
                    'time': -1
                }
            }, {
                '$group': {
                    '_id': '$cr',
                    'online': {
                        '$first': '$online'
                    }
                }
            }
        ]
        facet_instruction = {'$facet': {}}
        for cr in cr_list:
            facet_instruction['$facet'][cr] = [{
                '$match': {
                    '_id': cr,
                    'online': False
                }
            }]
        aggregate_instruction.append(facet_instruction)
        cursor = self.cr_history.aggregate(aggregate_instruction)
        result = {}
        for item in cursor:
            for cr_name, online_data in item.items():
                if online_data:
                    result[cr_name] = False
                else:
                    result[cr_name] = True
        return result


    def update_record(self, record_id, record):
        update_data = self.table.find_one_and_update(
            {'_id': ObjectId(record_id)},
            {'$set': {'record': record}}
        )
        return self.get_record(update_data['url'])[0]

    def batch_update_record(self, data):
        result = []
        for item in data:
            for key, value in item.items():
                data = self.table.find_one_and_update(
                    {'_id': key},
                    {'$set': {'record': value}}
                )
                result.append(self.get_record(data['url'])[0])
        return result

    def update_record_by_account(self, record, urls):
        result = []
        for url in urls:
            self.table.find_one_and_update(
                {'url': url},
                {'$set': {'record': record}},
                upsert=True
            )
            result.append(self.get_record(url)[0])
        return result

    def record_guider_history(self, guider_data):
        if 'id' in guider_data:
            del(guider_data['id'])
        guider_data['time'] = datetime.now()
        self.guider_history.insert(guider_data)

    def record_dist(self, link, cr):
        self.dist_table.insert({
            'link': link,
            'cr': cr,
            'datetime': datetime.now(),
            'monitor': True
        })

    def get_dist_history(self):
        cursor = self.dist_table.aggregate([
            {
                '$sort': {
                    'datetime': -1
                }
            }, {
                '$group': {
                    '_id': '$link',
                    'data': {
                        '$first': '$$ROOT'
                    }
                }
            }, {
                '$project': {
                    '_id': 0,
                    'link': '$data.link',
                    'cr': '$data.cr',
                    'datetime': '$data.datetime',
                    'monitor': '$data.monitor'
                }
            }
        ], allowDiskUse=True)
        return [x for x in cursor]

    def get_url_related_cr_name(self, url_list):
        aggregate_comm = [
            {
                '$sort': {
                    'datetime': -1
                }
            }, {
                '$group': {
                    '_id': '$link',
                    'cr': {
                        '$first': '$cr'
                    }
                }
            }
        ]
        facet_instruction = {'$facet': {}}
        for num, url in enumerate(url_list):
            facet_instruction['$facet'][str(num)] = [
                {
                    '$match': {
                        '_id': url
                    }
                }
            ]
        aggregate_comm.append(facet_instruction)
        cursor = self.dist_table.aggregate(aggregate_comm, allowDiskUse=True)
        data = [x for x in cursor]
        result = {}
        for item in data:
            for key, value in item.items():
                try:
                    value = value[0]
                    result[value['_id']] = value['cr']
                except (KeyError, IndexError):
                    self.logger.warning("{} 没有guider信息".format(facet_instruction['$facet'][key][0]['$match']['_id']))
                    continue
        return result

    def get_record(self, url=None):
        aggregate = [
            {
                '$project': {
                    '_id': 0,
                    'id': '$_id',
                    'url': '$url',
                    'record': '$record',
                }
            }]
        if url:
            aggregate.insert(0, {
                '$match': {
                    'url': url
                }
            })
        cursor = self.table.aggregate(aggregate, allowDiskUse=True)
        data = [x for x in cursor]
        return data

    def replace_monit(self, link):
        cursor = self.dist_table.aggregate([
            {
                '$match': {
                    'link': link,
                }
            }, {
                '$sort': {
                    'datetime': -1
                }
            }, {
                '$limit': 1
            }
        ])
        data = [x for x in cursor]
        data = data[0]
        cursor.close()
        sign = not data['monitor']
        self.dist_table.find_one_and_update(
            {'_id': data['_id']},
            {'$set': {'monitor': sign}}
        )
        return sign

    def get_single_guider(self, guider_id):
        cursor = self.table.aggregate([
            {
                '$match': {
                    'record.default.id': guider_id,
                }
            }, {
                '$limit': 1
            }, {
                '$replaceRoot': {
                    'newRoot': '$record.default'
                }
            }
        ])
        data = [x for x in cursor]
        if data:
            return data[0]
        else:
            return ''

    def get_cr_related_online_url(self, cr):
        cursor = self.dist_table.aggregate([
            {
                '$match': {
                    'cr': cr
                }
            }, {
                '$sort': {
                    'datetime': -1
                }
            }, {
                '$group': {
                    '_id': '$link',
                    'monitor': {
                        '$first': '$monitor'
                    }
                }
            }, {
                '$match': {
                    'monitor': True
                }
            }, {
                '$project': {
                    '_id': 1
                }
            }
        ])
        data = [x for x in cursor]
        if data:
            return [x['_id'] for x in data]
        else:
            return []

    def get_all_account(self):
        cursor = self.creativeData.aggregate(
            [
                {
                    '$match': {
                        'latest': 1
                    }
                }, {
                '$group': {
                    '_id': '$account'
                }
            }
            ]
        )
        data = [x for x in cursor]
        return [x['_id'] for x in data]

    def get_urls_by_account(self, account):
        cursor = self.creativeData.aggregate(
            [
                {
                    '$match': {
                        'latest': 1,
                        'account': account
                    }
                }, {
                '$group': {
                    '_id': '$matchUrl'
                }
            }
            ]
        )
        data = [x for x in cursor]
        return list(set([x['_id'] for x in data]))

    def __del__(self):
        self.conn.close()


def record_log(log_name='publish' + os.sep + 'logs' + os.sep + 'publish.log'):
    logger = logging.Logger(log_name)
    fh = logging.FileHandler(log_name, 'a', 'utf-8')
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)s] %(message)s', \
                                  datefmt='%y-%m-%d %H:%M:%S')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    return logger


def send_data_to_php(data, logger):
    new_data = {'record': {}}
    new_data['url'] = data['url']
    for time_str, info in data['record'].items():
        new_data['record'][time_str] = {}
        for key, value in info.items():
            if key == 'id':
                key = 'G_ID'
            elif key == 'img':
                key = 'url'
            new_data['record'][time_str][key] = value
    new_data = {'links': json.dumps(new_data)}
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    req = requests.Session()
    req.headers.update(headers)
    try:
        response = req.post(settings.PHP_INTERFACE, data=new_data)
        logger.info("send {} guider info to php success.".format(data['url']))
        logger.info("receive {} from php.".format(response.text))
    except Exception as e:
        logger.error("send {} guider info to php failed: {}".format(data['url'], str(e)))
    finally:
        return json.loads(response.text)


class Config(object):

    def __init__(self):
        self.filename = settings.HOST_CONFIG
        self.config = configparser.ConfigParser()

    def read_config(self):
        try:
            with open(self.filename, "r") as f:
                self.config.read_file(f)
            return self.config
        except Exception as e:
            logger = record_log()
            logger.error('read hosts.ini failed: {}'.format(str(e)))
            return False

    def get_data(self, host):
        if not self.read_config():
            return {'status': False}
        if host not in self.config.sections():
            return {'status': False}
        try:
            result = {
                'status': True,
                'user': self.config.get(host, 'ssh_user'),
                'port': self.config.get(host, 'ssh_port'),
                'private_key': self.config.get(host, 'ssh_private_key')
            }
            if not check_file(os.path.join(settings.PRIVATE_KEY_DIR, self.config.get(host, 'ssh_private_key'))):
                return {'status': False}
            return result
        except Exception:
            return {'status': False}
