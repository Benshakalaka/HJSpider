from views.ListenUsers import ListenUsers
from threading import Thread,current_thread
from queue import Queue
from HJSpider import Spider
import logging

class UserInfoGetter(Thread):
    def __init__(self, userQueue, limit, username, userpass, uidQueue):
        super(UserInfoGetter, self).__init__()
        self.uidQueue = uidQueue
        self.ListenUser = ListenUsers(
            userQueue, limit,
            loginUser=username,
            loginPass=userpass
        )

    def run(self):
        # 获取uid
        while True:
            uid = self.uidQueue.get(block=True)
            if uid is None:
                self.uidQueue.put(None)
                break
            self.ListenUser.appendUidPriority(uid)
            self.ListenUser.getOneUserUid()

            self.ListenUser.logger.info('信息获取成功 : ' + str(uid))

        self.ListenUser.logger.info('结束' + str(current_thread()))


def loggerInit():
    # 日志配置
    # 一般在简单的小脚本中才会用logging.basicConfig，因为稍大些每个模块的logger就需要分开
    # basicConfig配置后，会默认添加一个StreamHandler的，且获取的名为root的logger
    # 可参考 http://www.jb51.net/article/52022.htm
    # 输出到控制台的handler
    CHnadler = logging.StreamHandler()
    # 消息级别为WARNING及以上（级别分别是： NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL）
    CHnadler.setLevel(logging.INFO)
    # 输出到文件的handler
    FHandler = logging.FileHandler(filename='hjspider.log',
                                   mode='w',
                                   encoding='UTF-8')
    # 消息级别为DEBUG
    FHandler.setLevel(logging.DEBUG)
    # 设置格式
    formatter = logging.Formatter('%(thread)d %(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s:  %(message)s')
    # 设置格式
    CHnadler.setFormatter(formatter)
    FHandler.setFormatter(formatter)

    # 获取一个hjspider的logger（每个模块的logger都可以有一个名字，如果不指定则为root）
    logger = logging.getLogger('hjspider')
    # 将handler附加在这个logger上（handler可以理解为消息先传到logger，然后在传给每个handler处理）
    logger.addHandler(CHnadler)
    logger.addHandler(FHandler)
    # 既然消息是传到handler的，那么如果这个logger的level就和handler的level息息相关
    # 比如logger的level为info（默认）, 那么即使handler的level设置为debug，也不可能得到debug的消息
    # 每个handler的level在logger指定的level的基础上继续进行筛选
    logger.setLevel(logging.DEBUG)
    return logger

if __name__ == '__main__':
    loggerInit()


    UsersQueue = Queue()
    UidsQueue = Queue()

    cons1 = UserInfoGetter(UsersQueue, 0, 'benstep222@gmail.com', 'yuanhaitao123', UidsQueue)
    cons2 = UserInfoGetter(UsersQueue, 0, 'benstep222@163.com', 'yuanhaitao000', UidsQueue)
    prod = Spider(isLogin=False, userQueue=UsersQueue, uidQueue=UidsQueue)

    threads = [cons1, cons2, prod]
    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    print('over')

    # 因为访问频繁失败后，重新添加进优先队列，但是最外层循环却立刻加入新的id