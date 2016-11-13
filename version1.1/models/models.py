from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer ,String, DateTime, Date, SmallInteger, Float, ForeignKey, Index, UniqueConstraint
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

Engin = create_engine('mysql+pymysql://ben:@localhost:3306/HJSpider', max_overflow=5)
Base = declarative_base()

# 用户
class User(Base):
    __tablename__ = 'user'

    user_id = Column(String(10), primary_key=True, nullable=False)
    gender = Column(SmallInteger)
    nickName = Column(String(30))
    name = Column(String(30))
    signature = Column(String(100))
    introduction = Column(String(100))
    city = Column(String(30))
    registDate = Column(DateTime)
    lastSignin = Column(DateTime, index=True)
    signlast = Column(Integer)

# 节目
class Item(Base):
    __tablename__ = 'item'

    item = Column(String(30), primary_key=True, nullable=False)
    title = Column(String(50))
    imgUrl = Column(String(100))
    difficultLevel = Column(String(10))
    updateRate = Column(String(20))
    averageTime = Column(Integer)
    averageScore = Column(Float)


# 文章
class Article(Base):
    __tablename__ = 'article'

    article_id = Column(String(15), primary_key=True, nullable=False)
    item = Column(String(30), ForeignKey('item.item'))
    type = Column(String(10))
    title = Column(String(100))
    commentCount = Column(Integer)
    averageScore = Column(Float)
    timeLast = Column(Integer)
    publishTime = Column(DateTime)
    contributor = Column(String(10), ForeignKey('user.user_id'))
    difficultLevel = Column(String(10))
    rewards = Column(Integer)
    downloadUrl = Column(String(80))

# 文章标签
class ArticleTag(Base):
    __tablename__ = 'articletag'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tagName = Column(String(10), nullable=False)
    article = Column(String(15), ForeignKey('article.article_id'), nullable=False)

# 用户与文章
class UserListen(Base):
    __tablename__ = 'userlisten'

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    user = Column(String(10), ForeignKey('user.user_id'), nullable=False)
    article = Column(String(15), ForeignKey('article.article_id'), nullable=False)
    time = Column(Integer)
    score = Column(Float)
    reward = Column(Integer)
    listenDate = Column(Date, index=True)




class Models(object):

    def __init__(self, base, engine):
        self.base = base
        self.engine = engine
        self.session = (sessionmaker(bind=self.engine))()

    def createAll(self):
        self.base.metadata.create_all(self.engine)

    def dropAll(self):
        self.base.metadata.drop_all(self.engine)

    def clearAllData(self):

        # 注意删除顺序，不要引起一致性问题
        for i in self.session.query(ArticleTag).all():
            self.session.delete(i)
        for i in self.session.query(UserListen).all():
            self.session.delete(i)
        for i in self.session.query(Article).all():
            self.session.delete(i)
        for i in self.session.query(User).all():
            self.session.delete(i)
        for i in self.session.query(Item).all():
            self.session.delete(i)

        self.session.commit()


if __name__ == '__main__':
    models = Models(Base, Engin)
    # models.createAll()
    # models.dropAll()
    # models.clearAllData()


# 设置utf8哟，创建engin的时候最好也指定
# ALTER TABLE user DEFAULT CHARACTER SET utf8;
# ALTER TABLE article DEFAULT CHARACTER SET utf8;
# ALTER TABLE item DEFAULT CHARACTER SET utf8;
# ALTER TABLE articletag DEFAULT CHARACTER SET utf8;
# ALTER TABLE userlisten DEFAULT CHARACTER SET utf8;