from models import User, Article, Item
from datetime import datetime
from util import Utils

utils = Utils()

class UserInfo(object):
    def __init__(self, uid):
        # 用户ID
        self.__uid = uid
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
        # 性别, 0为female，1为male
        object.__setattr__(self, 'gender', -1)
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
        self.registDate = ''
        # 签到天数
        self.signinLast = 0
        # 最后登陆
        self.lastSignin = ''
        # 自我介绍
        self.selfIntroduction = ''

    @property
    def uid(self):
        return self.__uid

    def __setattr__(self, key, value):
        # 将性别以0，1存储，0为女，1为男
        if key == 'gender':
            if value != '':
                object.__setattr__(self, key, 1) if value == '男' else object.__setattr__(self, key, 0)
        else:
            object.__setattr__(self, key, value)

    def __str__(self):
        infoShow = '用户: '
        infoShow += ('uid : ' + self.__uid + '; ')
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


    def save(self, session):
        if session.query(User).get(self.__uid) is not None:
            return

        user = User(user_id=self.__uid, gender=self.gender, nickName=self.nickName, name=self.name,
                    signature=self.signature, introduction=self.selfIntroduction, city=self.city,
                    registDate=datetime.strptime(self.registDate, '%Y/%m/%d %H:%M:%S'),
                    lastSignin=utils.chinese2datetime(self.lastSignin),
                    signlast=self.signinLast)
        session.add(user)
        try:
            session.commit()
        except Exception:
            raise Exception


    # 获取留言列表
    def getRelatedInfoMessageList(self):
        pass

    # 获取碎碎列表
    def getRelatedInfoIngList(self):
        pass

    # 获取听写列表（被取消，在获取观众的时候对观众）
    # def getRelatedInfoListenList(self):
    #     pass




class ListenItemInfo(object):
    def __init__(self, url):
        self.__item = url.split('/')[-2]

        # 节目标题
        self.title = ''
        # 节目图片
        self.itemImgUrl = ''
        # 节目介绍
        self.introduction = ''
        # 节目分类
        self.type = []
        # 节目难度
        self.difficult = ''
        # 更新频率
        self.updateRate = ''
        # 平均用时,单位为秒
        # self.averageComsume = 0
        object.__setattr__(self, 'averageComsume', 0)
        # 平均得分
        self.averageScore = ''
        # 节目文章数量
        #self.articleAmount = 0
        # 听写次数（被注释）
        # self.listenTotalCount = 0

    def __setattr__(self, key, value):
        # 将x分x秒转换为秒
        if key == 'averageComsume':
            minutes = int(value.split('分')[0][0:2])
            seconds = int(value.split('分')[1][0:2])
            object.__setattr__(self, key, minutes * 60 + seconds)
        else:
            object.__setattr__(self, key, value)

    def save(self, session):
        if session.query(Item).get(self.__item) is not None:
            return

        item = Item(item=self.__item, title=self.title, imgUrl=self.itemImgUrl,
                    difficultLevel=self.difficult, updateRate=self.updateRate,
                    averageTime=self.averageComsume, averageScore=float(self.averageScore[0:-1]))
        session.add(item)
        try:
            session.commit()
        except Exception:
            raise Exception

    def __str__(self):
        infoShow = '节目: '
        infoShow += ('name : ' + self.__item + '; ')
        infoShow += ('title : ' + self.title + '; ')
        infoShow += ('itemImgUrl : ' + self.itemImgUrl + '; ')
        infoShow += ('introduction : ' + self.introduction + '; ')
        for t in self.type:
            infoShow += ('type : ' + t + '; ')
        infoShow += ('difficult : ' + self.difficult + '; ')
        infoShow += ('updateRate : ' + self.updateRate + '; ')
        infoShow += ('averageComsume : ' + str(self.averageComsume) + '; ')
        infoShow += ('averageScore : ' + str(self.averageScore) + '; ')
        # infoShow += ('articleAmount : ' + str(self.articleAmount) + '; ')
        return infoShow

class ListenArticleInfo(object):
    def __init__(self, uid):
        self.__uid = uid

        #所属节目
        self.item = ''
        # 类别
        self.type = ''
        # 文章标题
        self.title = ''

        # 评论人数
        self.commentCount = 0
        # 平均正确率
        self.averageScore = 0

        # 文章时长
        # self.timeLast = 0
        object.__setattr__(self, 'timeLast', 0)
        # 听写人数
        #self.listenCount = 0
        # 发布时间
        self.publishTime = ''
        # 贡献者(ID)
        self.contributorId = ''
        # 难度等级
        self.difficultLevel = ''
        # 文章标签
        self.tags = []
        # 奖励(单位：沪元)
        self.rewards = 0
        # 下载地址列表
        self.downloadUrl = ''


    def __setattr__(self, key, value):
        # 将文章时长转换为秒
        if key == 'timeLast':
            minutes = int(value.split(':')[0])
            seconds = int(value.split(':')[1])
            object.__setattr__(self, key, minutes * 60 + seconds)
        else:
            object.__setattr__(self, key, value)


    def save(self, session):
        if session.query(Article).get(self.__uid) is not None:
            return

        article = Article(article_id=self.__uid, item=self.item, type=self.type, title=self.title,
                          commentCount=self.commentCount, averageScore=self.averageScore,
                          timeLast=self.timeLast,
                          publishTime=datetime.strptime(self.publishTime, '%Y/%m/%d %H:%M:%S'),
                          contributor=self.contributorId, difficultLevel=self.difficultLevel,
                          rewards=int(self.rewards), downloadUrl=self.downloadUrl)
        session.add(article)
        try:
            session.commit()
        except Exception:
            raise Exception


    def __str__(self):
        infoShow = '文章: '
        infoShow += ('uid : ' + self.__uid + '; ')
        infoShow += ('type : ' + self.type + '; ')
        infoShow += ('title : ' + self.title + '; ')
        infoShow += ('commentCount : ' + str(self.commentCount) + '; ')
        infoShow += ('averageScore : ' + str(self.averageScore) + '; ')
        infoShow += ('timeLast : ' + str(self.timeLast) + '; ')
        infoShow += ('listenCount : ' + str(self.listenCount) + '; ')
        infoShow += ('publishTime : ' + self.publishTime + '; ')
        infoShow += ('contributorId : ' + str(self.contributorId) + '; ')
        infoShow += ('difficultLevel : ' + self.difficultLevel + '; ')
        infoShow += ('rewards : ' + str(self.rewards) + '; ')
        # infoShow += ('downloadUrl : ' + str(self.downloadUrl) + '; ')
        infoShow += ('tags : ' + str(self.tags) + '; ')

        return infoShow