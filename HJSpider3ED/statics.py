import re

def getTime(line, pattern):
    ret = pattern.search(line)
    if ret is not None:
        ret = int(float(ret.group(1)) * 10.0)

    return ret

if __name__ == '__main__':
    pattern = re.compile(r'时间：(\d+\.\d+)$')
    with open('hjspider.log', mode='r', encoding='utf-8') as f:
        while True:
            line = f.readline()
            if line is '':
                break
            time = getTime(line, pattern)
            if time is not None:
                print('#' * time)