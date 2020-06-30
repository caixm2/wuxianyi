# -*- coding: utf-8 -*-
"""
Created on Tue May 12 15:48:54 2020

@author: caixiaoming
"""

from __future__ import division

import datetime
import logging
import logging.handlers

import talib
import numpy as np
import pyttsx3

import requests
import copy
import csv
import os
import gc
import json
from collections import OrderedDict
from vtConstant import *
from threading import Thread
from qtpy.QtCore import Qt, QTimer
from qtpy import QtGui, QtCore
#from qtpy.QtWidgets import *

import ctaEngine
from ctaBase import *
from ctaTemplate import *
from vtObject import *
#from vtConstant import EMPTY_UNICODE, EMPTY_STRING, EMPTY_FLOAT, EMPTY_INT

###############################################################################
class MacdStrategy(CtaTemplate):
    '''MACD交易策略'''
    className = 'MacdStrategy'
    author = 'caixiaoming'
    version = "v1.3"
    """v1.0 建立版本号"""
    """v1.1 增加对商品期货10:15-10:30无数据的bar线处理"""
    """v1.2 添加指标金叉死叉语音提示"""
    """v1.3 周期提示增加bar.close信息，格式化时间输出去除毫秒 2020.06.29"""
    #vtSymbol = ''
    #exchange = ''
    
    # 参数列表，保存了参数的名称
    paramList = ['vtSymbol',
                 'OCM',
                 'maxPos',
                 'minPos',
                 'gridSize',
                 'profitSize']
    # 参数映射表
    paramMap = {'vtSymbol':u'交易合约',
                'exchange':u'交易所',
                'OCM'     :u'均线',
                'maxPos':u'最大手数',
                'minPos':u'最小手数',
                #'open_pos':u'交易手数',
                'gridSize':u'网格大小',
                'profitSize':u'赢利大小'
            }
    
    # 变量列表，保存了变量的名称
    varList = ['inited',
               'trading',
               'fastma0',
               'slowma0',
               'longPrice',
               'longPos',
               'shortPrice',
               'shortPos',
               'ypos0L',
               'ypos0S'
               ]
    
    #变量映射表
    varMap = {'inited' :u'初始化',
               'trading':u'交易中',
               'fastma0':u'快均线',
               'slowma0':u'慢均线',
               'longPrice':u'多单价格',
               'longPos':u'多单仓位',
               'shortPrice':u'空单价格',
               'shortPos':u'空单仓位',
               'ypos0L':u'昨多仓',
               'ypos0S':u'昨空仓'
            }
    
###############################################################################
    def __init__(self, ctaEngine=None, setting={}):
        super(MacdStrategy, self).__init__(ctaEngine, setting)
        self.ctaEngine = ctaEngine
        
        '''
        如果是多合约实例的话，变量需要放在__init__里面
        '''
        #self.widgetClass = KLWidget
        #self.widget = None
        
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            self.logger.setLevel(level = logging.INFO)
            #self.handler = logging.FileHandler('c:\\rb.txt')

            self.output(os.path.join(os.path.dirname(__file__), 'macd.txt'))
            self.handler = logging.FileHandler(os.path.join(os.path.dirname(__file__), 'macd.txt'))
            self.handler.setLevel(logging.WARNING)
            #self.formatter = logging.Formatter('%(asctime)s-%(levelname)s-%(messages)s')
            #self.handler.setFormatter(self.formatter)

            self.logger.addHandler(self.handler)
        
        self.vtSymbol = ''
        self.exchange = ''

        self.gridSize = 0
        self.profitSize = 0
        

        self.longPrice = 0.0
        self.shortPrice = 0.0
        self.longPos = 0
        self.shortPos = 0
        
        self.barList = []
        self.bufferSize = 60                         #需要缓存的数据的大小
        self.bufferCount = 0                          #已经缓存的数据计数
        self.highArray = np.zeros(self.bufferSize)    #K线最高价的数组
        self.lowArray = np.zeros(self.bufferSize)     #K线最低价的数组
        self.closeArray = np.zeros(self.bufferSize)   #K线收盘价的数组
        self.openArray = np.zeros(self.bufferSize)    #K线最高价的数组
        self.lastTick = None                          # 上一TICK缓存对象
        
        self.longSig = False
        self.shortSig = False
        
        self.fastma0 = 0
        self.slowma0 = 0

 
        self.initDays = 10      #初始化数据所用的天数默认30天
  
        self.OCM = 30           #操作分钟周期(1-60)默认30
        self.maxPos = 2         #开仓最大手数
        self.minPos = 1         #最小开单手数
    
        #策略变量
        self.bar = None                  #K线对象
        self.barMinute = ''              #K线当前的分钟
        self.minutebar = None            #minute K线对象
        #self.F = 10                       #快均线周期
        #self.S = 21                      #慢均线周期
    
        # 策略内部管理的仓位
        #pos = {}  # 总投机方向
        #tpos0L = {}  # 今持多仓
        #tpos0S = {}  # 今持空仓
        self.ypos0L = {}  # 昨持多仓
        self.ypos0S = {}  # 昨持空仓
        
        self.aubuy = "多开"
        self.aubuydone = "买入成交"
        self.ausell = "多平"
        self.auselldone = "卖出成交"

        self.aushort = "空开"
        self.aucover = "空平"
        
        self.output("version={0}".format(self.version))
    def onInit(self):
        #载入历史数据，并采用回话计算的方式初始化策略数值
        super(MacdStrategy, self).onInit()

        #self.getGui()
        self.putEvent()
        self.output('{0}策略onInit完成'.format(self.name))
        
    def onStart(self):
        super(MacdStrategy, self).onStart()
        #self.getGui()
        self.trading = False
        self.loadBar(self.initDays)
        self.getPricePos()
        #self.output('gridSize={0}, profitSize={1}, maxPos={2}, minPos={3}'.format(self.gridSize, self.profitSize, self.maxPos, self.minPos))
        self.trading = True
        self.putEvent()

        self.output('{0}策略onStart完成'.format(self.name))
        
    def onStop(self):
        super(MacdStrategy, self).onStop()

        self.putEvent()
        self.output('{0}策略onStop完成'.format(self.name))
        
    def onTick(self, tick):
        super(MacdStrategy, self).onTick(tick)
        '''
        {'investor':'', 'exchange':'IFFEX', 'vtSymbol':'IF2009','symbol':'IF2009', 'direction':'多', 'price':'3880', 'volume':'1'}
        '''
        
        # 过滤涨跌停和集合竞价
        if tick.lastPrice == 0 or tick.askPrice1==0 or tick.bidPrice1==0:
            return
        
        tickMinute = tick.datetime.minute
        if tickMinute != self.barMinute:
            self.barMinute = tickMinute      # 更新当前的分钟
            if self.bar:
                self.onBar(self.bar)
                
            bar = VtBarData()
            bar.vtSymbol = tick.symbol
            bar.symbol = tick.symbol
            bar.exchange = tick.exchange
            
            bar.open = tick.lastPrice
            bar.high = tick.lastPrice
            bar.low = tick.lastPrice
            bar.close = tick.lastPrice
            
            #bar.date = tick.date
            #bar.time = tick.time
            bar.datetime = tick.datetime     # K线的时间设为第一个tick时间
            bar.datetime = bar.datetime.replace(second=0, microsecond=0)  # 将秒和微秒设为0
            bar.date = bar.datetime.strftime('%Y%m%d')
            bar.time = bar.datetime.strftime('%H:%M:%S.%f')
            self.bar = bar                   # 这种写法为减少一层访问，加快速度

        else:
            bar = self.bar                   # 同样是为了加快速度
            
            bar.high = max(bar.high, tick.lastPrice)
            bar.low = min(bar.low, tick.lastPrice)
            bar.close = tick.lastPrice
            
    def onBar(self, bar):
        #self.output('onBar')
        #self.logger.info('onBar')
        
        if self.longSig and self.trading:
            if (self.longPos == 0) or (self.longPos > 0 and self.longPos < self.maxPos and (abs(bar.close - self.longPrice) > self.gridSize)):
                self.output('{0} {1} longpos==0 bar.close={2} longPrice={3}'.format(self.getDateTime(), self.vtSymbol, bar.close, self.longPrice))
                self.orderID = self.buy(bar.close, self.minPos)
                self.logger.warning('{0} {1} longpos==0 bar.close={2} longPrice={3}'.format(self.getDateTime(), self.vtSymbol, bar.close, self.longPrice))
                
            if self.shortPos < self.maxPos and self.shortPrice - bar.close >= self.profitSize:
                self.output('{0} {1} shortPos>=1 bar.close={2} shortPrice={3}'.format(self.getDateTime(), self.vtSymbol, bar.close, self.shortPos))
                self.orderID = self.cover(bar.close, self.minPos)
                self.logger.warning('{0} {1} shortPos>=1 bar.close={2} shortPrice={3}'.format(self.getDateTime(), self.vtSymbol, bar.close, self.shortPos))
            elif self.shortPos >= self.maxPos:
                self.output('{0} {1} shortPos>=maxPos bar.close={2} shortPrice={3}'.format(self.getDateTime(), self.vtSymbol, bar.close, self.shortPos))
                self.orderID = self.cover(bar.close, self.minPos)
                self.logger.warning('{0} {1} shortPos==maxPos bar.close={2} shortPrice={3}'.format(self.getDateTime(), self.vtSymbol, bar.close, self.shortPos))
                
            self.longSig = False
        if self.shortSig and self.trading:
            if (self.shortPos == 0) or (self.shortPos > 0 and self.shortPos < self.maxPos and (abs(bar.close - self.shortPrice) > self.gridSize)):
                self.output('{0} {1} short.pos==0 bar.close={2} shortPrice={3}'.format(self.getDateTime(), self.vtSymbol, bar.close, self.shortPrice))
                self.orderID = self.short(bar.close, self.minPos)
                self.logger.warning('{0} {1} short.pos==0 bar.close={2} shortPrice={3}'.format(self.getDateTime(), self.vtSymbol, bar.close, self.shortPrice))
                
            if self.longPos < self.maxPos and bar.close - self.longPrice >= self.profitSize:
                self.output('{0} {1} longPos >=1 bar.close={2} longPrice={3}'.format(self.getDateTime(), self.vtSymbol, bar.close, self.longPrice))
                self.orderID = self.sell(bar.close, self.minPos)
                self.logger.warning('{0} {1} longPos >=1 bar.close={2} longPrice={3}'.format(self.getDateTime(), self.vtSymbol, bar.close, self.longPrice))
            elif self.longPos >= self.maxPos:
                self.output('{0} {1} longPos>=maxPos bar.close={2} longPrice={3}'.format(self.getDateTime(), self.vtSymbol, bar.close, self.longPrice))
                self.orderID = self.sell(bar.close, self.minPos)
                self.logger.warning('{0} {1} longPos==maxPos bar.close={2} longPrice={3}'.format(self.getDateTime(), self.vtSymbol, bar.close, self.longPrice))
                
            self.shortSig = False
        
        if ((bar.datetime.minute + 1) % self.OCM == 0) or (self.minutebar and str(bar.datetime)[-8:] == '10:14:00' and (not self.minutebar.symbol[0:2] in ("IF","IC","IH"))):
            # 如果已经有聚合minute K线
            if self.minutebar:
                # 将最近分钟的数据更新到目前minute线中
                minutebar = self.minutebar
                minutebar.high = max(minutebar.high, bar.high)
                minutebar.low = min(minutebar.low, bar.low)
                minutebar.close = bar.close

                #if self.trading:
                #    self.output('{0} {1} minutebar0={2} {3}'.format(datetime.datetime.now(),self.vtSymbol, bar.datetime.minute, bar.datetime))
                #    self.logger.warning('{0} {1} minutebar0={2} {3}'.format(datetime.datetime.now(),self.vtSymbol, bar.datetime.minute, bar.datetime))
                    #self.recordLog('{0} minutebar0={1} {2}'.format(self.vtSymbol, bar.datetime.minute, bar.datetime))
                #推送minute线数据
                self.onminutebar(minutebar)
                #self.output(self.minutebar.datetime)
                #清空minute线数据缓存
                self.minutebar = None
                
        #elif self.minutebar and str(bar.datetime)[-8:] == '10:15:00' and (not self.minutebar.symbol[0:2] in ("IF","IC","IH")):
        #    self.output(bar.datetime)
        #    self.onminutebar(self.minutebar)
        #    self.minutebar = None

        else:
            # 如果没有缓存则新建缓存
            if not self.minutebar:
                minutebar = VtBarData()
                
                minutebar.vtSymbol = bar.vtSymbol
                minutebar.symbol = bar.symbol
                minutebar.exchange = bar.exchange
            
                minutebar.open = bar.open
                minutebar.high = bar.high
                minutebar.low = bar.low
                minutebar.close = bar.close
            
                minutebar.date = bar.date
                minutebar.time = bar.time
                minutebar.datetime = bar.datetime     # K线的时间设为第一个tick时间
            
                self.minutebar = minutebar

            else:
                minutebar = self.minutebar                   # 同样是为了加快速度
            
                minutebar.high = max(minutebar.high, bar.high)
                minutebar.low = min(minutebar.low, bar.low)
                minutebar.close = bar.close
        
        self.putEvent()
        #self.output('onBar完成')
        #self.logger.info('onBar完成')
        
    def onminutebar(self, bar):
        #self.output('onminutebar')
        #self.logger.info('onminutebar开始')
        # 保存K线数据
        self.closeArray[0:self.bufferSize-1] = self.closeArray[1:self.bufferSize]
        self.highArray[0:self.bufferSize-1] = self.highArray[1:self.bufferSize]
        self.lowArray[0:self.bufferSize-1] = self.lowArray[1:self.bufferSize]
        self.openArray[0:self.bufferSize-1] = self.openArray[1:self.bufferSize]
        #self.volumeArray[0:self.bufferSize-1] = self.volumeArray[1:self.bufferSize]
        self.closeArray[-1] = bar.close
        self.highArray[-1] = bar.high
        self.lowArray[-1] = bar.low
        self.openArray[-1] = bar.open
        #self.volumeArry[-1] = bar.volume
        
        # 判断缓存K线未达到设定值，继续累计
        self.bufferCount += 1
        if self.bufferCount < self.bufferSize:
            return
        #self.output(self.closeArray[0:29])

        # 计算指标数值

        dif, dea, hist = talib.MACD(self.closeArray, fastperiod=10, slowperiod=24, signalperiod=10)
        self.fastma0 = round(dif[-1], 1)
        self.slowma0 = round(dea[-1], 1)

        if self.trading:
            self.getPricePos()
            self.logger.warning('{0} {1} fastma={2}, slowma={3}, bar.close={4}'.format(self.getDateTime(), self.vtSymbol, self.fastma0, self.slowma0, bar.close))
            self.longSig = round(dif[-1], 1) > round(dea[-1], 1) and round(dif[-2], 1) <= round(dea[-2], 1)
            if self.longSig:
                self.output('{0} {1} longSig fast={2},slow={3}, longPos={4}, shortPos={5}, bar.close={6}'.format(self.getDateTime(), 
                                 self.vtSymbol, self.fastma0, self.slowma0, self.longPos, self.shortPos, bar.close))
                self.logger.warning('{0} {1} longSig fast={2},slow={3}, longPos={4}, shortPos={5}, bar.close={6}'.format(self.getDateTime(), 
                                 self.vtSymbol, self.fastma0, self.slowma0, self.longPos, self.shortPos, bar.close))
                self.playAudio(self.aubuy)
            self.shortSig = round(dif[-1], 1) < round(dea[-1], 1) and round(dif[-2], 1) >= round(dea[-2], 1)
            if self.shortSig:
                self.output('{0} {1} shortSig fast={2},slow={3}, longPos={4}, shortPos={5}, bar.close={6}'.format(self.getDateTime(), 
                                 self.vtSymbol, self.fastma0, self.slowma0, self.longPos, self.shortPos, bar.close))
                self.logger.warning('{0} {1} shortSig fast={2},slow={3}, longPos={4}, shortPos={5}, bar.close={6}'.format(self.getDateTime(), 
                                 self.vtSymbol, self.fastma0, self.slowma0, self.longPos, self.shortPos, bar.close))
                self.playAudio(self.aushort)
        

        # 发出状态更新事件
        self.putEvent()
        #self.output('onminutebar完成')
    def onOrder(self, order):
        pass
    
    def onTrade(self, trade):
        super(MacdStrategy, self).onTrade(trade,log=True)
        self.getPricePos()
        self.putEvent()
        
    def onStopOrder(self, so):
        pass
    
    def loadBar(self, days=9):
        #vtSymbol = 'IF2009'
        #exchange = 'CFFEX'
        if days > 30:
            self.output('最多预加载30天的历史1分钟K线数据，请修改参数')
            return
        
        # 将天数切割为3天以内的单元
        divisor, remainder = int(days / 3), days % 3
        days_list = [3] * divisor
        if remainder != 0:
            days_list.append(remainder)
            
        bars_list = []
        start_date = datetime.datetime.now().strftime('%Y%m%d')
        while len(days_list) > 0:
            _days = days_list.pop()
            bars = ctaEngine.getKLineData(self.vtSymbol, self.exchange, start_date, _days, 0)
            #with open('d:\\cta.txt', 'a') as f:
            #    f.writelines('{0} bars={1}\n'.format(datetime.datetime.now(),bars))
            #    f.close
            #self.logger.info('{0} bars={1}\n'.format(datetime.datetime.now(),bars))
            bars_list.append(bars)
            start_date = (datetime.datetime.strptime(bars[0].get('date'), '%Y%m%d') - datetime.timedelta(
                days=1)).strftime('%Y%m%d')
        bars_list.reverse()
        
        #self.logger.info('{0} bars_list={1}\n'.format(datetime.datetime.now(),bars_list))
        
        # 处理数据
        for _bars in bars_list:
            try:
                for _bar in _bars:
                    #self.logger.info('{0} _bar={1}\n'.format(datetime.datetime.now(),_bar))
                    bar = VtBarData()
                    bar.__dict__ = _bar
                    #func(bar)
                    self.onBar(bar)
            except Exception:
                self.output('历史数据获取失败，使用实盘数据初始化')

    def getPricePos(self):
        costinfos = self.get_investor_cost(self.vtSymbol)
        if costinfos:
            for costinfo in costinfos:
                for k, v in costinfo.items():
                    #self.output('{0}:{1}'.format(k, v))
                    if u'LONG' == costinfo['direction']:
                        self.longPrice = costinfo['open_avg_price']
                        self.longPos = costinfo['position']
                        self.ypos0L[self.vtSymbol] = self.longPos
                        #self.output('longPrice={0}'.format(self.longPrice))
                        #self.output('longPos={0}'.format(self.longPos))
                        #self.output('ypos0L={0}'.format(self.ypos0L[self.vtSymbol]))
                        break
                    if u'SHORT' == costinfo['direction']:
                        self.shortPrice = costinfo['open_avg_price']
                        self.shortPos = costinfo['position']
                        self.ypos0S[self.vtSymbol] = self.shortPos
                        #self.output('shortPrice={0}'.format(self.shortPrice))
                        #self.output('shortPos={0}'.format(self.shortPos))
                        #self.output('ypos0S={0}'.format(self.ypos0S[self.vtSymbol]))
                        break

    def recordLog(self, message, logLevel=logging.WARNING):
        logger = logging.getLogger(__name__)

        #self.output('logger')
        #if not self.logger.handlers:
        self.output('in')
        logger.setLevel(level = logging.INFO)
        handler = logging.FileHandler('d:\\rb.txt')
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s-%(levelname)s-%(messages)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
            
        self.output('ok')

        logger.warning(message)
        self.output('finish')
        logger.removeHandler(handler)

    def playAudio(self, word):
        engine = pyttsx3.init()
        engine.setProperty('rate', 160)

        words = (self.vtSymbol + word) * 2

        engine.say(words)
        engine.runAndWait()

    def getDateTime(self):
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        



