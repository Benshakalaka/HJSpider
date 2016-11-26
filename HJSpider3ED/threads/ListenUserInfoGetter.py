from views.ListenUsers import ListenUsers
from threading import Thread, current_thread
import logging

class UserInfoGetter(Thread):
    def __init__(self, limit, username, userpass, userQueue=None, uidQueue=None):
        super(UserInfoGetter, self).__init__()

        self.logger = logging.getLogger('hjspider.consumer')

        self.uidQueue = uidQueue
        self.ListenUser = ListenUsers(
            userQueue, limit,
            loginUser=username,
            loginPass=userpass
        )

    def run(self):
        # 获取uid
        while True:
            # 有时候因为访问频繁导致获取信息失败，此时就不能从queue中获取新的，而是要重复访问失败的
            if self.ListenUser.getPriorityLength() == 0:
                uid = self.uidQueue.get(block=True)
                if uid is None:
                    self.uidQueue.put(None)
                    break
                self.ListenUser.appendUidPriority(uid)

            userRet = self.ListenUser.getOneUserUid()
            if userRet is None:
                break
            uid, currTimeDelta = userRet

            self.logger.info('信息获取成功 : %s ; 消耗时间：%s' % (str(uid), str(currTimeDelta)))

        self.logger.info('Consumer : 此线程结束' + str(current_thread()))