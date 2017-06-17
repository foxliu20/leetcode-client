#!/usr/bin/env python3
import sys
import os
import urllib.request
import json
from retrying import retry
import configparser
from html.parser import HTMLParser

COOKIE = ""

def httpGet(url):
    req = urllib.request.Request(url)
    req.add_header("Cookie", COOKIE)
    return urllib.request.urlopen(req).read().decode()

def httpPostJson(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode())
    req.add_header("content-type", "application/json")
    req.add_header("Cookie", COOKIE)
    req.add_header("Host", "leetcode.com")
    req.add_header("Origin", "https://leetcode.com")
    req.add_header("Referer", "https://leetcode.com/problems/") # need problem name ?
    req.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.116 Safari/537.36")
    #req.add_header("X-CSRFToken", CSRF_TOKEN)
    req.add_header("X-Requested-With", "XMLHttpRequest")
    return urllib.request.urlopen(req).read().decode()

def getProblemList(category):
    url = "https://leetcode.com/api/problems/%s/" % category
    problems = json.loads( httpGet(url) )['stat_status_pairs']
    return problems

def getProblem(name):
    url = "https://leetcode.com/problems/%s/" % name
    html = httpGet(url)

    tag = '<meta name="description" content="'
    index = html.index(tag) + len(tag)
    desc = html[index:html.index('"', index)]
    hp = HTMLParser()
    desc = hp.unescape(desc)

    tag = 'codeDefinition:'
    index = html.index(tag) + len(tag)
    defaultCodes = json.loads( html[index:html.index('enableTestMode', index)].strip().replace("'", "\"")[:-3]+"]")

    tag = 'sampleTestCase:'
    index = html.index(tag) + len(tag)
    testcase = json.loads( html[index:html.index('\n', index)-1].replace("'", "\""))

    problem = {'desc':desc, 'codes':defaultCodes, 'testcase':testcase}
    return problem

def searchProblem(category, name):
    problems = getProblemList(category)
    problems = list( filter( lambda p: name in p['stat']['question__title_slug'], problems ))
    problems = sorted(problems, key = lambda p: p['stat']['question_id'])

    if len(problems) == 0:
        print("No problem matchs")
    for p in problems:
        print("%5s %6d %-80s %-6s" % (p['status'] if p['status'] != None else "", p['stat']['question_id'], p['stat']['question__title_slug'], {1:'Easy', 2:'Medium', 3:'Hard'}[p['difficulty']['level']]) )

def initProblem(category, question_id):
    problems = getProblemList(category)
    problems = list( filter( lambda p: question_id == p['stat']['question_id'], problems ))
    if len(problems) == 1:
        path = "./problems/%s/" % category
        if not os.path.exists(path): os.makedirs( path )
        p = problems[0]
        problemName = p['stat']['question__title_slug']
        p = getProblem( problemName )
        print( p['desc'] )
        with open("./desc", "w") as f:
            f.write(p['desc'])
        with open("./testcase", "w") as f:
            f.write(p['testcase'])
        cppCode = next(filter(lambda code:code['value'] == 'cpp', p['codes']))
        cppFile = "%s/%s.cpp" % (path, problemName)
        if not os.path.exists(cppFile):
            with open(cppFile, "wb") as f:
                f.write( cppCode['defaultCode'].encode() )
                print( "DefaultCode:" )
                print( cppCode['defaultCode'] )
        linkFile = "./algo.cpp"
        if os.path.exists(linkFile): os.unlink(linkFile)
        os.symlink(cppFile, linkFile)
        with open("./.working", "w") as f:
            f.write( "%s %s %d" % (category, problemName, question_id) )

def runLocal():
    os.system("g++ main.cpp -g -std=c++11")
    os.system("./a.out")

@retry(wait_fixed=2000)
def getSubmissionResult(interpret_id):
    interpret_url = 'https://leetcode.com/submissions/detail/%s/check/' % interpret_id
    result = json.loads( httpGet(interpret_url) )
    if result['state'] in ['STARTED', 'PENDING']:
        raise Exception
    return result

def runRemoteTest():
    with open("./.working", "r") as f:
        category, name, question_id = f.read().split(" ")
    with open("./algo.cpp", "r") as f:
        code = f.read()
    with open("testcase", "r") as f:
        testcase = f.read()
    print(code)
    url = "https://leetcode.com/problems/%s/interpret_solution/" % name
    data = {"data_input": testcase, "judge_type":"large", "lang":"cpp", "question_id":question_id, "test_mode":False, "typed_code":code}
    submission = json.loads( httpPostJson(url, data) )
    myResult = getSubmissionResult(submission['interpret_id'])
    expectedResult = getSubmissionResult(submission['interpret_expected_id'])
    print("Your Answer", myResult)
    print("Standard Answer", expectedResult)
    if 'compile_error' in myResult:
        print("Compile Error")
        print( myResult['compile_error'] )
        return
    if 'runtime_error' in myResult:
        print("RunTime Error")
        print( myResult['runtime_error'] )
        return

    if myResult['code_answer'] == expectedResult['code_answer']:
        status = "Accepted"
    else:
        status = "Wrong Answer"

    if myResult['code_output'] != []:
        print("STDOUT")
        for line in myResult['code_output']:
            print( line )
    print(status)

def submit():
    with open("./.working", "r") as f:
        category, name, question_id = f.read().split(" ")
    with open("./algo.cpp", "r") as f:
        code = f.read()
    with open("testcase", "r") as f:
        testcase = f.read()
    url = "https://leetcode.com/problems/%s/submit/" % name
    data = {"data_input": testcase, "judge_type":"large", "lang":"cpp", "question_id":question_id, "test_mode":False, "typed_code":code}
    submission = json.loads( httpPostJson(url, data) )
    myResult = getSubmissionResult(submission['submission_id'])
    print( myResult )


def requireArgv(num):
    if len(sys.argv) < num:
        usage()
        sys.exit()

def loadConfig():
    global COOKIE
    cp = configparser.SafeConfigParser()
    cp.read("config.ini")
    COOKIE = cp.get('profile', 'cookie')

def usage():
    print("Usage:")
    print("%s search <name>" % sys.argv[0])
    print("%s init <question_id>" % sys.argv[0])
    print("%s run" % sys.argv[0])
    print("%s test" % sys.argv[0])

def main():
    loadConfig()
    requireArgv(2)
    if sys.argv[1] == "search":
        requireArgv(3)
        searchProblem("algorithms", sys.argv[2])
    if sys.argv[1] == "init":
        requireArgv(3)
        initProblem("algorithms", int(sys.argv[2]))
    if sys.argv[1] == "run":
        runLocal()
    if sys.argv[1] == "test":
        runRemoteTest()
    if sys.argv[1] == "submit":
        submit()

if __name__ == '__main__':
    main()
