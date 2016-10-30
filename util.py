import hashlib
import re
from datetime import datetime, timedelta

class Utils(object):

    # 获取md5加密后的值
    def md5_encode(self, string):
        m = hashlib.md5()
        m.update(string.encode())
        md5value=m.hexdigest()
        return md5value

    # 根据queryParams对象，创建url
    def urlCreate(self, host, queryParams):
        paramTemp = ''
        for key,value in queryParams.items():
            paramTemp += ('&' + str(key) + '=' + str(value))

        host += paramTemp[1:]
        return host

    # 将['x年前', 'x个月前', 'x天前', 'x小时前', 'x分钟前']转为datetime类型
    def chinese2datetime(self, string):
        timeValue = int(re.compile(r'(\d+)').search(string).group(1))
        timeObj = None

        for type in ['年', '月', '天', '小时', '分钟', '秒']:
            if string.find(type) != -1:
                current = datetime.now()

                if type is '年':
                    timeObj = current - timedelta(days=(timeValue * 365))
                elif type is '月':
                    timeObj = current - timedelta(days=(timeValue * 30))
                elif type is '天':
                    timeObj = current - timedelta(days=timeValue)
                elif type is '小时':
                    timeObj = current - timedelta(hours=timeValue)
                elif type is '分钟':
                    timeObj = current - timedelta(minutes=timeValue)
                else:
                    timeObj = current - timedelta(seconds=timeValue)
        return timeObj

