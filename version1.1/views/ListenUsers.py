from ..models.ListenUser import ListenUser

class ListenUsers(object):
    '''
    input: 某文章的uid
    output: 暂无
    '''
    def __init__(self):
        # 传入的要访问的文章uid
        self.fromUids = []
        # 下一个要访问的uid的下标
        self.fromUidsIndex = -1

    # 添加文章uid
    def appendFromUid(self):
        pass

    # 根据传入的uid获取用户
    def getUsersFromUid(self):


        #根据传入的url获取ajax所需的参数
        commentId = articleUid.split('/')[-2][2:8]

        form = {}
        postUrl = 'http://ting.hujiang.com/ajax.do'

        headers = {
            "Host": "ting.hujiang.com",
            "Content-Length": "83",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.84 Safari/537.36",
            "Content-Type": "application/json; charset=UTF-8"
        }

        form = {}
        form['classMethod'] = 'AjaxComs.GetListenedUserList'
        form['param'] = [1, int(commentId), 0]
        form['pageName'] = None

        try:
            # 需要先走一个，看看总共多少个听众，可以分多少页，即多少次请求(每次7个人)
            content = requests.post(postUrl, data=json.dumps(form), headers=headers)
        except Exception:
            self.logger.error('第一次获取某文章听众失败: ' + articleUrl)
            return

        try:
            contentText = content.text
            contentJson = json.loads(contentText)
        except Exception:
            self.logger.error('第一次json 解析文章听众失败: ' + articleUrl)
            return

        try:
            listenUserCount = int(contentJson['d'][1])
        except:
            self.logger.error('第一次获取的ajax数据错误，该页用户未被获取: ' + articleUrl)
            listenUserCount = 0

        totalPages = int(listenUserCount / 7)
        if listenUserCount % 7 != 0:
            totalPages += 1

        self.logger.info('该文章听众数量：' + str(listenUserCount) + '; 页数: ' + str(totalPages))
        for i in range(1,totalPages+1):
            self.logger.info('第 ' + str(i) + ' 页用户, 当前 ' + str(self.userCurrentCount) + ' 用户(不包括302)')
            form['param'][0] = i

            try:
                content = requests.post(postUrl, data=json.dumps(form), headers=headers)
            except Exception:
                self.logger.error('获取文章id的2-8位为' + str(form['param'][1]) + ' 第' + str(i) + '页失败！')
                continue

            try:
                contentText = content.text
                contentJson = json.loads(contentText)
            except Exception:
                self.logger.error('JSON解析文章id的2-8位为' + str(form['param'][1]) + ' 第' + str(i) + '页失败！')
                continue

            try:
                userInfoContainer = BeautifulSoup(contentJson['d'][2], "lxml")
            except Exception:
                self.logger.error('BeautifulSoup解析文章id的2-8位为' + str(form['param'][1]) + ' 第' + str(i) + '页失败！')
                continue

            userList = userInfoContainer.find_all(class_='userListItemIcon')
            if not userList:
                continue

            for user in userList:
                uid = user.find('a')['userid']
                if uid in self.usersAll:
                    continue

                getUserInfoStart = time.time()

                time2sleep = self.timeIntervalBase * 2 ** self.tooFrequent
                if time2sleep >= 2.0:
                    self.logger.warning('程序将沉睡'+str(time2sleep) + '秒以避免访问过于频繁')
                # 太快容易引发大量虚假302
                time.sleep(time2sleep)
                # 更换代理地址

                self.getUserInfo(uid)
                getUserInfoEnd = time.time()

                self.logger.info('访问此用户消耗时间（秒）：' + str(getUserInfoEnd - getUserInfoStart))

                if self.userCurrentCount == self.userLimit_Max:
                    self.isOverLimited = True
                    self.logger.info('用户数量达到限制，退出！')
                    break

            if self.isOverLimited:
                break

    # 获取用户信息
    def getUserInfo(self):
        pass
