from .models import User
from util import Utils
from datetime import datetime

# 处理多个用户
class ListenUser(object):

    def __init__(self, url):
        # 用户主页
        self.url = url
        # 访客数量
        #self.viewCount = 0
        # 留言数量
        #self.msgCount = 0
        # 留言列表
        # 留言的评论时间有问题，一年以内（365天以内）没有年份
        #self.msgList = []
        # 碎碎数量（http://t.hujiang.com/u/3566854/）
        # 不要被显示的页数欺骗，其实有很多页，可以通过ul标签是否有li元素判断这一页是否有碎碎，没有则表示结束
        #self.ingCount = 0
        # 碎碎列表
        #self.ingList = []
        # 日志数量
        #self.blogCount = 0
        # 听写数量
        #self.listenCount = 0
        # 听写列表
        #self.listenList = []
        # 口语数量
        #self.talkCount = 0
        # 礼物数量
        #self.giftCount = 0
        # 昵称
        self.nickName = ''
        # 名称
        self.name = ''
        # 签名
        self.signature = ''
        # 城市
        self.city = ''
        # 沪龄(用注册时间代替)
        #self.yearLast = ''
        # 注册时间
        self.registDate = '1970/1/1 0:0:0'
        # 签到天数
        self.signinLast = 0
        # 最后登陆
        self.lastSignin = ''
        # 自我介绍
        self.selfIntroduction = ''
        # 性别, 0为female，1为male
        object.__setattr__(self, 'gender', -1)

    @property
    def uid(self):
        '获取用户uid'
        return self.url.split('/')[-2]

    def __setattr__(self, key, value):
        # 性别以0，1存储，0为女，1为男，-1为未填写
        if key == 'gender':
            if value != '':
                object.__setattr__(self, key, 1) if value == '男' else object.__setattr__(self, key, 0)
        else:
            object.__setattr__(self, key, value)

    def save(self, session):
        if session.query(User).get(self.uid) is not None:
            return

        user = User(user_id=self.uid, gender=self.gender, nickName=self.nickName, name=self.name,
                    signature=self.signature, introduction=self.selfIntroduction, city=self.city,
                    registDate=datetime.strptime(self.registDate, '%Y/%m/%d %H:%M:%S'),
                    lastSignin=Utils.chinese2datetime(self.lastSignin),
                    signlast=self.signinLast)

        try:
            session.add(user)
            session.commit()
        except Exception:
            raise Exception

    def __str__(self):
        infoShow = '用户: '
        infoShow += ('uid : ' + self.uid + '; ')
        infoShow += ('name : ' + self.name + '; ')
        infoShow += ('nickName : ' + self.nickName + '; ')
        infoShow += ('gender : ' + str(self.gender) + '; ')
        # infoShow += ('yearLast : ' + self.yearLast + '; ')
        infoShow += ('city : ' + self.city + '; ')
        infoShow += ('registDate : ' + self.registDate + '; ')
        infoShow += ('signinLast : ' + str(self.signinLast) + '; ')
        infoShow += ('lastSignin : ' + self.lastSignin + '; ')
        # infoShow += ('viewCount : ' + str(self.viewCount) + '; ')
        # infoShow += ('msgCount : ' + str(self.msgCount) + '; ')
        # infoShow += ('ingCount : ' + str(self.ingCount) + '; ')
        # infoShow += ('blogCount : ' + str(self.blogCount) + '; ')
        # infoShow += ('listenCount : ' + str(self.listenCount) + '; ')
        # infoShow += ('talkCount : ' + str(self.talkCount) + '; ')
        # infoShow += ('giftCount : ' + str(self.giftCount) + '; ')
        infoShow += ('selfIntroduction : [[[' + self.selfIntroduction + ']]]')
        return infoShow