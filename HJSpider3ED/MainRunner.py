from threads.HJSpider import Spider
from threads.ListenUserInfoGetter import UserInfoGetter
from queue import Queue
import configparser
import logging
import time

class MainSpider(object):
    # 线程最大数量为提供的账号密码组数量
    def __init__(self, consumerCount=1):
        self.logger = logging.getLogger('hjspider.main')
        self.logger.info('MAIN SPIDER START ...')
        self.config_privacy = configparser.ConfigParser()
        # 用户名密码配置文件username,password两个属性
        self.config_privacy.read('config/ConfigUser.conf', encoding='utf-8')

        self.consumerCount = min(consumerCount, int(self.config_privacy.get('info', 'count')))
        # 获取所需要的用户名、密码组；如果消耗者为0，表示要单线程，那么也需要一组用户名密码的
        user_pass_couples = [
            (
                self.config_privacy.get('32'+str(i+1), 'username'),
                self.config_privacy.get('32'+str(i+1), 'password')
            )
            for i in range(max(self.consumerCount, 1))
        ]

        self.userQueue = (None if self.consumerCount == 0 else Queue())
        self.uidQueue = (None if self.consumerCount == 0 else Queue(maxsize=self.consumerCount*3))

        # 一个生成者足以
        self.productor = Spider(isLogin=False,
                                userQueue=self.userQueue,
                                uidQueue=self.uidQueue) \
            if self.consumerCount > 0 else \
                        Spider(user_name=user_pass_couples[0][0],
                               password=user_pass_couples[0][1])


        # 消耗着数量待定（消耗者爬取用户数量一般为无限制，由生产者控制）
        self.consumers = [
            UserInfoGetter(
                limit=0,
                username=user_pass_couples[i][0],
                userpass=user_pass_couples[i][1],
                userQueue=self.userQueue,
                uidQueue=self.uidQueue
            )
            for i in range(self.consumerCount)
        ]

    def run(self):
        self.productor.start()
        for consumer in self.consumers:
            consumer.start()

    def join(self):
        self.productor.join()
        for consumer in self.consumers:
            consumer.join()


if __name__ == '__main__':
    timeStart = time.time()
    spider = MainSpider(consumerCount=3)
    spider.run()
    spider.join()
    logging.shutdown()
    timeEnd = time.time()
    timeDelta = timeEnd - timeStart
    print('耗时：' + str(timeDelta) + ' 秒')


# uidQueue要不要加限制，不然指定了超大的，一直在跑这个了