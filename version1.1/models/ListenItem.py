from .models import Item

# 处理单个节目的页面
class ListenItem(object):

    def __init__(self, url):
        # 节目链接
        self.url = url
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
        # 平均得分
        self.averageScore = ''
        # 节目文章数量
        #self.articleAmount = 0
        # 听写次数（被注释）
        # self.listenTotalCount = 0
        # 平均用时,单位为秒
        # self.averageComsume = 0
        object.__setattr__(self, 'averageComsume', 0)

    @property
    def item(self):
        '获取节目名称'
        return self.url.split('/')[-2]

    def __setattr__(self, key, value):
        # 将x分x秒转换为秒
        if key == 'averageComsume':
            minutes = int(value.split('分')[0][0:2])
            seconds = int(value.split('分')[1][0:2])
            object.__setattr__(self, key, minutes * 60 + seconds)
        else:
            object.__setattr__(self, key, value)

    def save(self, session):
        if session.query(Item).get(self.item) is not None:
            return

        item = Item(item=self.item, title=self.title, imgUrl=self.itemImgUrl,
                    difficultLevel=self.difficult, updateRate=self.updateRate,
                    averageTime=self.averageComsume, averageScore=float(self.averageScore[0:-1]))

        try:
            session.add(item)
            session.commit()
        except Exception:
            raise Exception
