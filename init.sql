create database HJSpider;

create table User(
    user_id char(10) primary key not null, 
    gender tinyint(1), 
    nickName varchar(30), 
    name varchar(30),
    signature varchar(100),
    introduction varchar(100),
    city varchar(30),
    yearLast int,
    registDate datetime,
    lastSignin datetime
);

create table ListenItem(
    itemName varchar(30) primary key not null,
    title varchar(50) not null,
    imgUrl varchar(100),
    difficultLevel char(10),
    updateRate varchar(20),
    averageTime int,
    averageScore float(5,1),
    itemType varchar(10)
);


create table ListenArticle(
    article_id char(15) primary key not null,
    item varchar(30),
    type varchar(10),
    title varchar(100),
    commentCount int,
    averageScore float(5,1),
    timeLast int,
    publishTime date,
    contributor char(10),
    difficultLevel char(10),
    rewards int,
    downloadUrl varchar(100),
    foreign key(item) references ListenItem(itemName),
    foreign key(contributor) references User(user_id)
);


create table ArticleTag(
    id int UNSIGNED NOT NULL AUTO_INCREMENT primary key,
    tagName varchar(10) not null,
    article char(15) not null,
    foreign key(article) references ListenArticle(article_id)
);


create table UserListen(
    user char(10) not null,
    article char(15) not null,
    time int,
    score float(5,1),
    reward int,
    listenDate date,
    primary key(user, article)
);


ALTER TABLE user DEFAULT CHARACTER SET utf8;
ALTER TABLE article DEFAULT CHARACTER SET utf8;
ALTER TABLE item DEFAULT CHARACTER SET utf8;
ALTER TABLE  DEFAULT CHARACTER SET utf8;
ALTER TABLE  DEFAULT CHARACTER SET utf8;
