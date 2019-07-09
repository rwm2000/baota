#!/usr/bin/python
#coding: utf-8

import os
import json
import time
import datetime
import re

import public


class Monitor:
    def __init__(self):
        pass

    def __get_file_json(self, filename):
        try:
            if not os.path.exists(filename): return {}
            return json.loads(public.readFile(filename))
        except:
            return {}

    def _get_site_list(self):
        sites = public.M('sites').where('status=?', (1,)).field('name').get()
        return sites

    def _statuscode_distribute_site(self, site_name):
        today = time.strftime('%Y-%m-%d', time.localtime())
        path = '/www/server/total/total/' + site_name + '/request/' + today + '.json'

        day_401 = 0
        day_500 = 0
        day_502 = 0
        day_503 = 0
        if os.path.exists(path):
            spdata = self.__get_file_json(path)

            for c in spdata.values():
                for d in c:
                    if '401' == d: day_401 += c['401']
                    if '500' == d: day_500 += c['500']
                    if '502' == d: day_502 += c['502']
                    if '503' == d: day_503 += c['503']

        return day_401, day_500, day_502, day_503

    def _statuscode_distribute(self, args):
        sites = self._get_site_list()

        count_401, count_500, count_502, count_503 = 0, 0, 0, 0
        for site in sites:
            site_name = site['name']
            day_401, day_500, day_502, day_503 = self._statuscode_distribute_site(site_name)
            count_401 += day_401
            count_500 += day_500
            count_502 += day_502
            count_503 += day_503
        return {'401': count_401, '500': count_500, '502': count_502, '503': count_503}

    # 获取mysql当天的慢查询数量
    def _get_slow_log_nums(self, args):
        if not os.path.exists('/etc/my.cnf'):
            return 0

        ret = re.findall(r'datadir\s*=\s*(.+)', public.ReadFile('/etc/my.cnf'))
        if not ret:
            return 0
        filename = ret[0] + '/mysql-slow.log'

        if not os.path.exists(filename):
            return 0

        count = 0
        zero_point = int(time.time()) - int(time.time() - time.timezone) % 86400
        with open(filename) as f:
            for line in f:
                line = line.strip().lower()
                if line.startswith('set timestamp='):
                    timestamp = int(line.split('=')[-1].strip(';'))
                    if timestamp >= zero_point:
                        count += 1
        return count

    # 判断字符串格式的时间是不是今天
    def _is_today(self, time_str):
        try:
            time_date = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").date()
        except:
            try:
                time_date = datetime.datetime.strptime(time_str, "%y%m%d %H:%M:%S").date()
            except:
                time_date = datetime.datetime.strptime(time_str, "%d-%b-%Y %H:%M:%S").date()
        today = datetime.date.today()
        if time_date == today:
            return True
        return False

    # PHP慢日志
    def _php_count(self, args):
        result = 0
        if not os.path.exists('/www/server/php'):
            return result

        for i in os.listdir('/www/server/php'):
            if os.path.isdir('/www/server/php/' + i):
                php_slow = '/www/server/php/' + i + '/var/log/slow.log'
                if os.path.exists(php_slow):
                    php_info = open(php_slow, 'r')
                    for j in php_info.readlines():
                        if re.search(r'\[\d+-\w+-\d+.+', j):
                            time_str = re.findall(r'\[\d+-\w+-\d+\s+\d+:\d+:\d+\]', j)
                            time_str = time_str[0].replace('[', '').replace(']', '')
                            if self._is_today(time_str):
                                result += 1
                            else:
                                break

        return result

    # 获取攻击数
    def _get_attack_nums(self, args):
        file_name = '/www/server/btwaf/total.json'
        if not os.path.exists(file_name): return 0

        try:
            file_body = json.loads(public.readFile(file_name))
            return int(file_body['total'])
        except:
            return 0

    def get_exception(self, args):
        data = {'mysql_slow': self._get_slow_log_nums(args), 'php_slow': self._php_count(args), 'attack_num': self._get_attack_nums(args)}
        statuscode_distribute = self._statuscode_distribute(args)
        data.update(statuscode_distribute)
        return data

    # 获取蜘蛛数量分布
    def get_spider(self, args):
        today = time.strftime('%Y-%m-%d', time.localtime())
        sites = self._get_site_list()

        data = {}
        for site in sites:
            site_name = site['name']
            file_name = '/www/server/total/total/' + site_name + '/spider/' + today + '.json'
            if not os.path.exists(file_name): continue
            day_data = self.__get_file_json(file_name)
            for s_data in day_data.values():
                for s_key in s_data.keys():
                    if s_key not in data:
                        data[s_key] = s_data[s_key]
                    else:
                        data[s_key] += s_data[s_key]
        return data

    # 获取负载和上行流量
    def load_and_up_flow(self, args):
        import psutil

        load_five = float(os.getloadavg()[1])
        cpu_count = psutil.cpu_count()

        up_flow = 0
        data = public.M('network').dbfile('system').field('up').order('id desc').limit("5").get()
        if len(data) == 5:
            up_flow = round(sum([item['up'] for item in data]) / 5, 2)

        return {'load_five': load_five, 'cpu_count': cpu_count, 'up_flow': up_flow}

    # 取每小时的请求数
    def get_request_count_by_hour(self, args):
        today = time.strftime('%Y-%m-%d', time.localtime())

        request_data = {}
        sites = self._get_site_list()
        for site in sites:
            path = '/www/server/total/total/' + site['name'] + '/request/' + today + '.json'
            if os.path.exists(path):
                spdata = self.__get_file_json(path)
                for hour, value in spdata.items():
                    count = value.get('GET', 0) + value.get('POST', 0)
                    if hour not in request_data:
                        request_data[hour] = count
                    else:
                        request_data[hour] = request_data[hour] + count

        return request_data

    # 取服务器的请求数
    def _get_request_count(self, args):
        request_data = self.get_request_count_by_hour(args)
        return sum(request_data.values())

    # 获取瞬时请求数和qps
    def get_request_count_qps(self, args):
        from BTPanel import cache

        cache_timeout = 86400

        old_total_request = cache.get('old_total_request')
        otime = cache.get("old_get_time")
        if not old_total_request or not otime:
            otime = time.time()
            old_total_request = self._get_request_count(args)
            time.sleep(2)
        ntime = time.time()
        new_total_request = self._get_request_count(args)

        qps = int(round(float(new_total_request - old_total_request) / (ntime - otime)))

        cache.set('old_total_request', new_total_request, cache_timeout)
        cache.set('old_get_time', ntime, cache_timeout)
        return {'qps': qps, 'request_count': new_total_request}