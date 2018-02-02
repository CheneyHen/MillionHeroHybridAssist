# -*- coding:utf-8 -*-

"""

    Xi Gua video Million Heroes

"""


import multiprocessing
from multiprocessing import Event
from multiprocessing import Pipe

import threading
from threading import Thread
import time
from argparse import ArgumentParser
from multiprocessing import Value

import re
import operator
from functools import partial
from terminaltables import AsciiTable

from config import api_key
from config import api_version
from config import app_id
from config import app_key
from config import app_secret
from config import data_directory
from config import enable_chrome
from config import image_compress_level
from config import prefer
from config import crop_areas
from core.android import analyze_current_screen_text
from core.android import save_screen
from core.baiduzhidao import baidu_count
from core.bingqa import bing_count
from core.check_words import parse_false
from core.chrome_search import run_browser
from core.ocr.baiduocr import get_text_from_image as bai_get_text
from core.ocr.spaceocr import get_text_from_image as ocrspace_get_text

global isNegativeQuestion
global origQuestion
isNegativeQuestion = False
origQuestion = ""

if prefer[0] == "baidu":
    get_text_from_image = partial(bai_get_text,
                                  app_id=app_id,
                                  app_key=app_key,
                                  app_secret=app_secret,
                                  api_version=api_version,
                                  timeout=5)
elif prefer[0] == "ocrspace":
    get_test_from_image = partial(ocrspace_get_text, api_key=api_key)

def parse_args():
    parser = ArgumentParser(description="Million Hero Assistant")
    parser.add_argument(
        "-t", "--timeout",
        type=int,
        default=5,
        help="default http request timeout"
    )
    return parser.parse_args()


def parse_question_and_answer(text_list):
    global origQuestion
    question = ""
    start = 0
    for i, keyword in enumerate(text_list):
        question += keyword
        if "?" in keyword:
            start = i + 1
            break
        elif "？" in keyword: # 增加中文问号判断
            start = i + 1
            break
    real_question = question.split(".")[-1]
    origQuestion = real_question
    # 新增题目模式识别
    global isNegativeQuestion
    isNegativeQuestion = False
    if real_question.find('没有')>=0 or real_question.find('未')>=0 or real_question.find('不是')>=0 or real_question.find('是错')>=0:
        isNegativeQuestion = True
        real_question = real_question.replace('没有','有')
        real_question = real_question.replace('未', '')
        real_question = real_question.replace('还未', '已')
        real_question = real_question.replace('不是', '是')
        real_question = real_question.replace('是错', '是对')
    question, true_flag = parse_false(real_question)
    # 增加识别异常符号处理
    for ii in range(start,len(text_list)):
        text_list[ii] = re.sub("[\s+\.\!\/_,《》√✔×✘↘→↗↑↖←↙↓\“\”·$%^*(+\’\‘\']+|[+——！，。？、~@#￥%……&*（）]+", "", text_list[ii])
        text_list[ii] = text_list[ii].lower()
    return true_flag, real_question, question, text_list[start:]


def pre_process_question(keyword):
    """
    strip charactor and strip ?
    :param question:
    :return:
    """
    for char, repl in [("“", ""), ("”", ""), ("？", "")]:
        keyword = keyword.replace(char, repl)
    keyword = keyword.split(r"．")[-1]
    keywords = keyword.split(" ")
    keyword = "".join([e.strip("\r\n") for e in keywords if e])
    return keyword


class SearchThread(Thread):
    def __init__(self, question,answer,timeout,engine):
        Thread.__init__(self)
        self.question = question
        self.answer = answer
        self.timeout = timeout
        self.engine = engine
    def run(self):
        if self.engine == 'baidu':
            self.result = baidu_count(self.question,self.answer,timeout=self.timeout)
        else:
            self.result = bing_count(self.question,self.answer,timeout=self.timeout)
    def get_result(self):
        return self.result

def main():
    args = parse_args()
    timeout = args.timeout

    if enable_chrome:
        closer = Event()
        noticer = Event()
        closer.clear()
        noticer.clear()
        reader, writer = Pipe()
        browser_daemon = multiprocessing.Process(
            target=run_browser, args=(closer, noticer, reader,))
        browser_daemon.daemon = True
        browser_daemon.start()

    def __inner_job():
        global isNegativeQuestion,origQuestion
        start = time.time()
        text_binary = analyze_current_screen_text(
            directory=data_directory,
            compress_level=image_compress_level[0],
            crop_area = crop_areas[game_type]
        )
        keywords = get_text_from_image(
            image_data=text_binary,
        )
        if not keywords:
            print("本题不能够识别！")
            return

        true_flag, real_question, question, answers = parse_question_and_answer(keywords)
        print('-' * 60)
        print(origQuestion)
        print('-' * 60)
        print("\n".join(answers))

        # notice browser
        if enable_chrome:
            writer.send(question)
            noticer.set()

        search_question = pre_process_question(question)
        thd1 = SearchThread(search_question, answers, timeout, 'baidu')
        thd2 = SearchThread(search_question, answers, timeout, 'bing')
        # 创立双并发线程
        if __name__ == '__main__':
            thd1.setDaemon(True)
            thd1.start()
            thd2.setDaemon(True)
            thd2.start()
            # 顺序开启两线程
            thd1.join()
            thd2.join()
            # 等待两线程执行结束
        summary = thd1.get_result()
        summary2 = thd2.get_result()
        # 获取线程执行结果

        # 下面开始合并结果并添加可靠性标志
        creditFlag = True
        credit = 0
        summary_t = summary
        for i in range(0,len(summary)):
            summary_t[answers[i]] += summary2[answers[i]]
            credit += summary_t[answers[i]]
        if credit < 2:
            creditFlag = False

        if isNegativeQuestion == False:
            summary_li = sorted(summary_t.items(), key=operator.itemgetter(1), reverse=True)
        else:
            summary_li = sorted(summary_t.items(), key=operator.itemgetter(1), reverse=False)
        data = [("选项", "权重")]
        topscore = 0
        for a, w in summary_li:
            if w > topscore:
                topscore = w
        for a, w in summary_li:
            if isNegativeQuestion==False:
                data.append((a, w))
            else:
                data.append((a, topscore-w))
        table = AsciiTable(data)
        print(table.table)

        print("*" * 60)
        if creditFlag == False:
            print("        ！！！ 本题预测结果不是很可靠，请三思后行 ！！！\n        ！！！ 本题预测结果不是很可靠，请三思后行 ！！！")
        if isNegativeQuestion==True:
            print("        --- 本题是否定提法，程序已帮您优化结果！ ---")
        if true_flag:
            print("+ 建议选项 ： ", summary_li[0][0])
            print("- 排除选项 ： ", summary_li[-1][0])
        else:
            print("+ 建议选项 ： ", summary_li[0][0])
            print("- 排除选项 ： ", summary_li[-1][0])
        print("*" * 60)

        end = time.time()
        print("耗时 {0} 秒".format(end - start))
        save_screen(
            directory=data_directory
        )

    print("""
    原作者：GitHub/lingfengsan
    Branch作者：GitHub/leyuwei
    Branch改进：优化算法的匹配模式
                新增否定题搜索识别模式
                新增双线程并发搜索
                修正BUG们
    请选择答题节目: 
      1. 百万英雄
      2. 冲顶大会
    请务必在开始前将游戏评论区进行右滑关闭
    """)
    game_type = input("输入游戏编号: ")
    if game_type == "1":
        game_type = '百万英雄'
    elif game_type == "2":
        game_type = '冲顶大会'
    else:
        game_type = '百万英雄'

    while True:
        print("""
    请在答题开始前运行程序，
    答题开始的时候按Enter预测答案
                """)
        
        print("当前选择答题游戏: {}\n".format(game_type))

        enter = input("按Enter键开始，按ESC键退出...")
        if enter == chr(27):
            break
        try:
            __inner_job()
        except Exception as e:
            print(str(e))

        print("=" * 72)

    if enable_chrome:
        reader.close()
        writer.close()
        closer.set()
        time.sleep(3)


if __name__ == "__main__":
    main()
