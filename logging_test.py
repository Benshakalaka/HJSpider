import logging




class test(object):
    def __init__(self):
        self.logger = logging.getLogger('hjspider')
        CHnadler = logging.StreamHandler()
        CHnadler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s:  %(message)s')
        CHnadler.setFormatter(formatter)

        self.logger.addHandler(CHnadler)
        self.logger.setLevel(logging.DEBUG)

        self.logger.error('start')

a = test()



# # 日志配置
#         # 输出到控制台的handler
#         # CHnadler = logging.StreamHandler()
#         # 消息级别为WARNING及以上（级别分别是： NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL）
#         # CHnadler.setLevel(logging.NOTSET)
#         # 输出到文件的handler
#         # FHandler = logging.FileHandler(filename='hjspider.log',
#         #                               mode='w',
#         #                               encoding = 'UTF-8')
#         # 消息级别为INFO
#         # FHandler.setLevel(logging.DEBUG)
#         # 设置格式
#         # formatter = logging.Formatter('%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s:  %(message)s')
#         # 设置格式
#         # CHnadler.setFormatter(formatter)
#         # FHandler.setFormatter(formatter)
#         hdr = logging.StreamHandler()
#         formatter = logging.Formatter('[%(asctime)s] %(name)s:%(levelname)s: %(message)s')
#         hdr.setFormatter(formatter)
#
#         self.logger = logging.getLogger('hjspider')
#         # self.logger.addHandler(CHnadler)
#         # self.logger.addHandler(FHandler)
#         self.logger.addHandler(hdr)
#         self.logger.setLevel(logging.DEBUG)
#
#         # test
#         self.logger.warning('start')
#         logging.shutdown()
#         exit(1)