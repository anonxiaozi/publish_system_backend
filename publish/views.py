from django.shortcuts import render, HttpResponse, redirect
from django.http import JsonResponse
from django.views import View
from django.conf import settings
import os
from publish import tools, generate_site, operate_gitlab
from urllib.parse import urlparse
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
import check_site
import threading
from bson import json_util
from bson.objectid import ObjectId
import json


# Create your views here.


logger = tools.record_log()


class TemplateView(View):

    def get(self, request):
        l = []
        for item in os.listdir(settings.CR_TEMPLATE_PATH):
            if os.path.isdir(os.path.join(settings.CR_TEMPLATE_PATH, item)):
                l.append(item)
        l.sort()
        mongodb = tools.ConnectDB(args=settings.MONGODB_INFO)
        result = mongodb.get_cr_list_online_status(l)
        result = {'status': 200, 'message': result}
        return JsonResponse(result, safe=False)


class ModifyStatus(View):
    def get(self, request, cr, status):
        status = bool(int(status))
        mongodb = tools.ConnectDB(args=settings.MONGODB_INFO)
        mongodb.record_cr_online(cr, status)
        logger.warn("change cr '{}' status: {}".format(cr, status))
        if not status:
            mongodb.replace_monit_from_cr(cr, status)
            url_list = mongodb.get_cr_related_link(cr)
            change_url_monitor = check_site.CheckURL()
            result = []
            for url in url_list:
                result.append({'url': url, 'sign': status})
            change_url_monitor.url_dict = result
            change_url_monitor.record(change_url_monitor.domain_dict)
            logger.warn("change urls status to {}: {}".format(status, url_list))
        action = '上线' if status else '下线'
        cr_status = mongodb.get_signle_cr_online_status(cr)
        return JsonResponse({'status': 200, 'message': '{} {} 成功'.format(action, cr), 'data': cr_status})


class DistributeView(View):

    mongodb = tools.ConnectDB(args=settings.MONGODB_INFO)

    @staticmethod
    def _result(status, message):
        return {'status': status, 'message': message}

    def single_dist(self, cr_name, url, result):
        url_parse = urlparse(url)
        domain_name = url_parse.netloc
        path = url_parse.path.lstrip('/').rsplit('/', 1)[0]
        cr_dir = os.path.join(settings.CR_TEMPLATE_PATH, cr_name)
        gene_site = generate_site.GenerateSiteConf(cr_dir, domain_name, path)
        ssh_result = gene_site.run()
        if isinstance(ssh_result, str) or not ssh_result:
            data = '更新失败：{}'.format(str(ssh_result))
        else:
            self.mongodb.record_dist(url, cr_name)
            data = '更新成功'
        logger.error('{} 更新结果: {}'.format(url, data))
        result.append({'url': url, 'status': data})

    def get(self, request, cr_name):
        """
        批量更新使用模板的站点
        """
        url_list = self.mongodb.get_cr_related_online_url(cr_name)
        logger.warn("Start update cr: {} \n url_list: {}".format(cr_name, url_list))
        result = []
        thread_list = []
        for url in url_list:
            t = threading.Thread(target=self.single_dist, args=(cr_name, url, result))
            thread_list.append(t)
        for thread in thread_list:
            thread.daemon = True
            thread.start()
        for t in thread_list:
            t.join()
        logger.info("Update cr: {} \n result: {}".format(cr_name, result))
        return JsonResponse({'status': 200, 'message': result}, safe=False)

    def post(self, request):
        cr_name = request.POST.get('cr_name')
        url = request.POST.get('url')
        if not cr_name or not url:
            return JsonResponse(self._result(500, '信息不全'))
        if url.endswith('index.html') or url.endswith('/'):
            online_result = self.mongodb.get_cr_list_online_status([cr_name])
            online_result = online_result[cr_name]
            if not online_result:
                return JsonResponse(self._result(500, '发布失败: 首先确保文案 <{}> 上线'.format(cr_name)))
            url_parse = urlparse(url)
            domain_name = url_parse.netloc
            path = url_parse.path.lstrip('/').rsplit('/', 1)[0]
            cr_dir = os.path.join(settings.CR_TEMPLATE_PATH, cr_name)
            gene_site = generate_site.GenerateSiteConf(cr_dir, domain_name, path)
            ssh_result = gene_site.run()
            if isinstance(ssh_result, str) or not ssh_result:
                return JsonResponse(self._result(500, '发布失败：连接服务器失败<{}>'.format(str(ssh_result))))
            self.mongodb.record_dist(url, cr_name)
            check = self.mongodb.get_record(url)
            if not check:
                self.mongodb.insert_record({'url': url, 'record': {'default': {}}})
            return JsonResponse(self._result(200, '发布成功：{0}'.format(url)))
        else:
            return JsonResponse(self._result(500, 'URL不规范：{}'.format(url)))


class GuiderView(View):

    mongodb = tools.ConnectDB(args=settings.MONGODB_INFO)

    @staticmethod
    def _result(status, message, data=None):
        if data:
            return {'status': status, 'message': message, 'data': data}
        else:
            return {'status': status, 'message': message}

    def get(self, request):
        guider_data = self.mongodb.get_record()
        url_list = [x['url'] for x in guider_data]
        url_cr_dict = self.mongodb.get_url_related_cr_name(url_list)
        for item in guider_data:
            for record, value in item['record'].items():
                if record == "default":
                    value['start_time'] = value['end_time'] = record
                else:
                    value['start_time'] = record.split('-')[0]
                    value['end_time'] = record.split('-')[-1]
            try:
                item['cr'] = url_cr_dict[item['url']]
            except KeyError:
                item['cr'] = ''
            finally:
                item['id'] = json_util.dumps(item['id'])
        return JsonResponse(self._result(200, guider_data), safe=False)

    def post(self, request):
        record_id = ObjectId(json_util.loads(request.POST.get('record_id')))
        records = json.loads(request.POST.get('record'))
        result = {}
        for record, record_info in records.items():
            for key, value in record_info.items():
                if not value:
                    return JsonResponse(self._result(500, "{} 的数据不完整".format(record)))
            if record == 'default':
                time_str = 'default'
            elif len(record_info['start_time']) == 1:
                time_str = '{}-{}'.format(record_info['start_time'], record_info['end_time'])
            elif not record.startswith('new'):
                start_str = datetime.strptime(record_info['start_time'], '%Y-%m-%d %H:%M:%S').strftime('%Y%m%d%H%M%S')
                end_str = datetime.strptime(record_info['end_time'], '%Y-%m-%d %H:%M:%S').strftime('%Y%m%d%H%M%S')
                time_str = '{}-{}'.format(start_str, end_str)
            else:
                start_str = datetime.strptime(record_info['start_time'], '%Y-%m-%d %H:%M:%S').strftime('%Y%m%d%H%M%S')
                end_str = datetime.strptime(record_info['end_time'], '%Y-%m-%d %H:%M:%S').strftime('%Y%m%d%H%M%S')
                time_str = '{}-{}'.format(start_str, end_str)
            for key in ['start_time', 'end_time', 'choice']:
                if key in record_info:
                    del(record_info[key])
            result[time_str] = record_info
        doc = self.mongodb.update_record(record_id, result)
        logger.info("update guider[{}] data".format(record_id))
        self.mongodb.record_guider_history(doc)
        logger.info("record {} guider change info".format(record_id))
        if '_id' in doc:
            del(doc['_id'])
        php_status = tools.send_data_to_php(doc, logger)
        message = ''
        status = 200
        if php_status['code'] == 200:
            status = 200
            message = '{}文案信息更新成功, 上传数据成功'.format(doc['url'])
        else:
            status = 500
            message = '{}文案信息更新成功, 上传数据失败'.format(doc['url'])
        for record, value in doc['record'].items():
            if record == "default":
                value['start_time'] = value['end_time'] = record
            else:
                value['start_time'] = record.split('-')[0]
                value['end_time'] = record.split('-')[-1]
        return JsonResponse(self._result(status, message, doc))


@csrf_exempt
def pull_view(request):
    logger = tools.record_log()
    try:
        git = operate_gitlab.OperateGit(settings.GITLAB_URL, settings.GITLAB_TOKEN)
        git.pull_object()
        logger.info("pull html templates from gitlab success.")
    except Exception as e:
        logger.info("pull html templates from gitlab failed: {}".format(str(e)))
        return HttpResponse('failed. {}'.format(str(e)))
    return HttpResponse('ok.')


class GetDistHistory(View):

    def get(self, request):
        mongo = tools.ConnectDB(args=settings.MONGODB_INFO)
        dist_list = mongo.get_dist_history()
        cr_list = [x['cr'] for x in dist_list]
        result = mongo.get_cr_list_online_status_2(cr_list)
        dist_result = []
        for dist in dist_list:
            if 'datetime' not in dist:
                continue
            if result[dist['cr']]:
                dist_result.append(dist)
        dist_result.sort(key=lambda x:x['datetime'], reverse=True)
        return JsonResponse({'status': 200, 'message': dist_result}, safe=False)


class MonitorView(View):

    def post(self, request):
        link = request.POST.get('link')
        conn = tools.ConnectDB(args=settings.MONGODB_INFO)
        sign = conn.replace_monit(link)
        change_url_monitor = check_site.CheckURL()
        change_url_monitor.url_dict = [{'url': link, 'sign': sign}]
        change_url_monitor.record(change_url_monitor.domain_dict)
        return JsonResponse({"status": 200, "message": "监控状态修改成功", "data": sign})


class AccountUrls(View):

    mongodb = tools.ConnectDB(args=settings.MONGODB_INFO)

    @staticmethod
    def _result(status, message, data=None):
        if data:
            return {'status': status, 'message': message, 'data': data}
        else:
            return {'status': status, 'message': message}

    def get(self, request, account=None):
        if account:
            urls = self.mongodb.get_urls_by_account(account)
            return JsonResponse(self._result(200, urls), safe=False)
        else:
            accounts = self.mongodb.get_all_account()
            accounts.sort()
            return JsonResponse(self._result(200, accounts), safe=False)

    def post(self, request):
        logger = tools.record_log()
        urls = json.loads(request.POST.get('urls'))
        if not urls:
            return JsonResponse(self._result(500, 'urls is null'))
        records = json.loads(request.POST.get('record'))
        result = {}
        for record, record_info in records.items():
            for key, value in record_info.items():
                if not value:
                    return JsonResponse(self._result(500, "{} 的数据不完整".format(record)))
            if record == 'default':
                time_str = 'default'
            elif len(record_info['start_time']) == 1:
                time_str = '{}-{}'.format(record_info['start_time'], record_info['end_time'])
            else:
                start_str = datetime.strptime(record_info['start_time'], '%Y-%m-%d %H:%M:%S').strftime('%Y%m%d%H%M%S')
                end_str = datetime.strptime(record_info['end_time'], '%Y-%m-%d %H:%M:%S').strftime('%Y%m%d%H%M%S')
                time_str = '{}-{}'.format(start_str, end_str)
            for key in ['start_time', 'end_time', 'choice']:
                if key in record_info:
                    del(record_info[key])
            result[time_str] = record_info
        doc = self.mongodb.update_record_by_account(result, urls)
        logger.info("Update guider information in batch via account success: \nUrls: {}\nRecord info: {}".format(', '.join(urls), result))
        for item in doc:
            self.mongodb.record_guider_history(item)
            logger.info("Record guider change info: {}".format(item))
            if '_id' in item:
                del(item['_id'])
        #    tools.send_data_to_php(item, logger)
        return JsonResponse(self._result(200, '批量更新文案成功'))
