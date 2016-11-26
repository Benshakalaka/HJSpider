from views.ListenUsers import ListenUsers
from threading import Thread,current_thread
from queue import Queue
from threads.HJSpider import Spider
from util import Utils

if __name__ == '__main__':
    Utils.loggerInit('hjspider')