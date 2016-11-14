from .models import Article
from datetime import datetime

# 处理多个包含多篇文章的页面
class ListenArticle(object):

    def __init__(self, url):
        # 文章地址
        self.url = url

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
         # 文章时长，默认是01:12这种形式
        object.__setattr__(self, 'timeLast', 0)

    @property
    def uid(self):
        '获取文章uid'
        return self.url.split('/')[-2]

    def __setattr__(self, key, value):
        # 将文章时长转换为秒,默认是01:12这种形式
        if key == 'timeLast':
            minutes = int(value.split(':')[0])
            seconds = int(value.split(':')[1])
            object.__setattr__(self, key, minutes * 60 + seconds)
        else:
            object.__setattr__(self, key, value)

    def save(self, session):
        if session.query(Article).get(self.uid) is not None:
            return

        article = Article(article_id=self.uid, item=self.item, type=self.type, title=self.title,
                          commentCount=self.commentCount, averageScore=self.averageScore,
                          timeLast=self.timeLast,
                          publishTime=datetime.strptime(self.publishTime, '%Y/%m/%d %H:%M:%S'),
                          contributor=self.contributorId, difficultLevel=self.difficultLevel,
                          rewards=int(self.rewards), downloadUrl=self.downloadUrl)
        
        try:
            session.add(article)
            session.commit()
        except Exception:
            raise Exception