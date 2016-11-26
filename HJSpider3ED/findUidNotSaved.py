# 从日志中筛选出获取到的用户uid， 与数据库中存储的进行比较
# 之后查找该uid在日志中出现的位置，进行bug fix

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer ,String, DateTime, Date, SmallInteger, Float, ForeignKey, Index, UniqueConstraint
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.models import User
import re

def test():
    content =''

    with open('hjspider.log', mode='r', encoding='utf-8') as f:
        content = f.read()

    list = re.compile(r'信息获取成功 : (\d+) ;').findall(content)

    return list


Engin = create_engine('mysql+pymysql://ben:@localhost:3306/HJSpider', max_overflow=5)
session = (sessionmaker(bind=Engin))()
query = session.query(User)
uids = test()
for uid in uids:
    if query.get(uid) is None:
        print(uid)

