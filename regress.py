
# STDLIB
import argparse
import filecmp
import multiprocessing
import os
import queue
import shutil
import subprocess
import sys
import threading
import time

from astropy.io import fits


def cleanTree(src, ignore=None, function=os.remove):
    # based on copy of shutil.copytree
    names = os.listdir(src)
    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    errors = []
    for name in names:
        if name in ignored_names:
            continue
        srcname = os.path.join(src, name)
        try:
            if os.path.isdir(srcname):
                cleanTree(srcname, ignore, function)
            else:
                # Will raise a SpecialFileError for unsupported file types
                function(srcname)
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except Error as err:
            errors.extend(err.args[0])
        except EnvironmentError as why:
            errors.append((srcname, str(why)))
    if errors:
        raise Error(errors)

def makeOutputDir(outPath, ignoreError=False):
    # create output dir
    try:
        os.mkdir(outPath)
    except FileExistsError:
        if ignoreError:
            return
        sys.exit('Error: The output path "{0}" already exists, please delete or use another path'.format(outPath))
    except:
        if ignoreError:
            return
        else:
            raise
    logPath = os.path.join(outPath, 'logs')
    os.mkdir(logPath)

def moveTree(src, dst, ignore=None):
    shutil.copytree(src, dst, ignore=ignore, copy_function=shutil.move)

def walkAndFindFiles(path, suffix, keyword, value):

    fileList = set()
    value = str.lower(value)
    if value == 't' or value == 'true':
        value = True
    elif value == 'f' or value == 'false':
        value = False

    for root, subDir, files in os.walk(path, topdown=True, followlinks=False):
        for fname in files:
            if suffix in fname:
                fullFilePath = os.path.join(root, fname)
                try:
                    hdu = fits.open(fullFilePath, ignore_missing_end=True)
                except OSError as err:
                    pass  # do nothing
                valueFound = hdu[0].header[keyword]

                if valueFound == None:
                    hdu.close()
                    continue
                hdu.close()

                if type(valueFound) is bool:
                    if valueFound == value:
                        fileList.add(fullFilePath)
                elif value == str.lower(valueFound):
                    fileList.add(fullFilePath)
    return fileList


def findFilesInList(list, keyword, value):
    newList = set()
    value = str.lower(value)
    if value == 't' or value == 'true':
        value = True
    elif value == 'f' or value == 'false':
        value = False

    for entry in list:
        hdu = fits.open(entry)
        found = hdu[0].header[keyword]
        if found == None:
            hdu.close()
            continue
        hdu.close()

        if type(found) is bool:
            if found == value:
                newList.add(entry)
        elif value == str.lower(found):
            newList.add(entry)
    return newList

def formatSeconds(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return '{0}hrs:{1}mins:{2}secs'.format(h, m, s)

class AtomicCounter():
    def __init__(self, value=0):
        self.count = value
        self.lock = threading.Lock()

    def inc(self, value=1):
        with self.lock:
            self.count += value

    def dec(self, value=1):
        with self.lock:
            self.count -= value

    def get(self):
        with self.lock:
            return self.count

    def set(self, value=0):
        with self.lock:
            self.count = value

nPassed = AtomicCounter()
nFailed = AtomicCounter()

class TestQueueItem:
    def __init__(self, _testFile, _cmd, _outPath):
        self.testFile = _testFile
        self.cmd = _cmd
        self.outPath = _outPath
        self.version = self.getVersion()
        self.results = None

        logPath = os.path.join(self.outPath, 'logs')
        logFile = os.path.basename(self.testFile) + '.log'
        self.logFile = os.path.join(logPath, logFile)

    def run(self):
        os.chdir(self.outPath)

        print('Processing "{0}"...'.format(self.testFile))

        self.results = subprocess.run(['time', self.cmd, "-v", self.testFile], shell=False, check=False, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if self.results.returncode:
            print('"{0}" failed'.format(self.testFile))
            nFailed.inc()
        else:
            print('"{0}" succeeded'.format(self.testFile))
            nPassed.inc()

    def log(self):
        try:
            fid = open(self.logFile, mode='w')
        except OSError as err:
            print('ERROR: Cannot write log file "{0}" due to:'.format(self.logFile))
            print('"{0}"'.format(err))
        else:
            fid.write('Input file: "{0}"\n'.format(self.testFile))
            fid.write('Program: "{0}"\n'.format(self.cmd))
            fid.write('Version: {0}\n'.format(str(self.version)))
            fid.write('return code:{0}\n\n'.format(str(self.results.returncode)))
            fid.write('stdout results:\n {0}\n\n'.format(str(self.results.stdout)))
            fid.write('stderr results:\n {0}\n\n'.format(str(self.results.stderr)))
            fid.close()

    def getVersion(self):
        try:
            return subprocess.run([self.cmd, "--version"], shell=False, check=False, stdout=subprocess.PIPE, universal_newlines=True).stdout
        except:
            return None


def compareResults(path1, path2, outPath):

    def countSuffixOnly(list, suffix):
        count = 0
        if suffix:
            for entry in list:
                if entry.endswith(suffix):
                    count = count + 1
        else:
            count = len(list)
        return count

    def countDiff(parentCmp, suffix=None):
        count = countSuffixOnly(parentCmp.diff_files, suffix)
        for subDir in parentCmp.subdirs.values():
            count = count + countDiff(subDir)
        return count

    def countLeftOnly(parentCmp, suffix=None):
        count = countSuffixOnly(parentCmp.left_only, suffix)
        for subDir in parentCmp.subdirs.values():
            count = count + countLeftOnly(subDir)
        return count

    def countRightOnly(parentCmp, suffix=None):
        count = countSuffixOnly(parentCmp.right_only, suffix)
        for subDir in parentCmp.subdirs.values():
            count = count + countRightOnly(subDir)
        return count

    def recursiveFITSDiff(parentCmp):
        # for entry in parentCmp.common_files:



        for subDir in parentCmp.subdirs.values():
            recursiveFITSDiff(subDir)

    if path1 == None or path2 == None or outPath == None:
        return

    # test paths
    if os.path.exists(path1) == False:
        sys.exit('ERROR: the path, "{0}", given to diff does not exist'.format(path1))
    if os.path.exists(path2) == False:
        sys.exit('ERROR: the path, "{0}", given to diff does not exist'.format(path2))
    if os.path.exists(outPath) == False:  # could mkdir
        sys.exit('ERROR: the output path, "{0}", does not exist'.format(outPath))

    # Quick dir comparison for simple stats
    dirDiff = filecmp.dircmp(path1, path2)
    nDiff = countDiff(dirDiff)
    nLogsDiff = countDiff(dirDiff, '.log')
    print('\n{0} file(s) differ between paths - {1} of them log files'.format(nDiff, nLogsDiff))
    print('{0} orphaned file(s)/dir(s) found - {1} of them log files'.format(countLeftOnly(dirDiff), countLeftOnly(dirDiff, '.log')))
    print('{0} newly generated file(s)/dir(s) found - {1} of them log files\n'.format(countRightOnly(dirDiff), countRightOnly(dirDiff, '.log')))

    if nDiff == 0:
        print('Regression PASSED! All files identical')
        return
    elif nDiff == nLogsDiff:
        print('Regression LOOSELY PASSED! Only log files differ')
        return

    # FITSDiff common files
    recursiveFITSDiff(dirDiff)

def printList(list):
    for entry in list:
        print(entry)


def main(argv):
    print('\n')
    startTime = time.time()

    # Define command line arguments
    parser = argparse.ArgumentParser(description='Regression test suite')
    parser.add_argument('-r', dest='regressionPath', metavar='<root data path>', nargs=1, type=str,
                             help='Root path to regression test data', default='./')
    parser.add_argument('-o', '--outPath', metavar='<output path>', dest='outPath', nargs=1,
                             help='Root path to dump all output', default='./')
    parser.add_argument('-e', '--execPath', metavar='<path containing executable>', dest='execPath', nargs=1,
                             help='Root path to executables', default=os.environ['PATH'])
    parser.add_argument('-D', '--diffOnly', metavar='<dir to diff>', dest='diffOnly', nargs=2,
                             help='Do not run tests, only compare output in first dir to that in second')
    parser.add_argument('-d', '--diffOnTheFly', metavar='<dir to diff>', dest='diffOnTheFly', nargs=1,
                             help='Diff each current test output in <out path> to those in <path to output to diff>. Do this after each test is complete')
    parser.add_argument('--cte', dest='cteOnly', action='store_true', default=False,
                            help='Only complete tests and comparisons for files with PCTECORR = PERFORM')
    parser.add_argument('--clean', dest='clean', nargs=1, default=None,
                            help='Clean <root data path> leaving only *raw.fits files.')
    parser.add_argument('--move', metavar='<path>', dest='move', nargs=2, default=None,
                            help='Move all none *raw.fits files in <1st path> to <2nd path>/results')
    parser.add_argument('-n', '--maxThreads', dest='maxThreads', nargs=1, default=multiprocessing.cpu_count(),
                            help='The maximum number of threads to use to spawn jobs')
    parser.add_argument('--find', dest='optFind', nargs='*', default=None,
                            help='Recurse through 1st arg <path> for files with 2nd arg <keyword> \
                            set to 3rd arg <value> and print all found')
    args = parser.parse_args(argv)

    if args.optFind != None:
        if len(args.optFind) < 3:
            print('ERROR: incorrect number of arguments for --find')
            return
        length = len(args.optFind)
        foundSet = walkAndFindFiles(args.optFind[0], 'raw.fits', args.optFind[1], args.optFind[2])
        if length > 3:
            for i in range(3, length, 3):
                op = args.optFind[i]
                keyword = args.optFind[i + 1]
                value = args.optFind[i + 2]
                if str.lower(op) == 'and':
                    foundSet = findFilesInList(foundSet, keyword, value)
                elif str.lower(op) == 'or':
                    foundSet = foundSet | findFilesInList(foundSet, keyword, value)
        printList(foundSet)  # use set to dedup
        print('{0} files found'.format(len(foundSet)))
        return

    if args.move and len(args.move) == 2:
        # Move all generated output in regressionPath to outPath/results
        src = args.move[0]
        dst = args.move[1]
        makeOutputDir(dst, ignoreError=True)
        dst = os.path.join(dst, 'results')
        print('Moving all none *raw.fits files in "{0}" to "{1}".'.format(src, dst))
        moveTree(src, dst, ignore=shutil.ignore_patterns('*raw.fits'))
        return

    if args.clean and len(args.clean) == 1:
        print('Cleaning: removing all none *raw.fits files from "{0}"'.format(args.clean[0]))
        cleanTree(args.clean[0], ignore=shutil.ignore_patterns('*raw.fits'))
        return

    if args.diffOnly and len(args.diffOnly) == 2:
        compareResults(args.diffOnly[0], args.diffOnly[1], args.outPath[0])
        print('\nTime taken to diff: {0} (seconds)'.format(str(time.time() - startTime)))
        return

    if args.diffOnTheFly and len(args.diffOnTheFly) == 1:
        diffOnTheFly = True
        comparisonPath = args.diffOnTheFly[0]
        return
    else:
        diffOnTheFly = False

    outPath = args.outPath[0]
    regressionPath = args.regressionPath[0]
    execPath = args.execPath[0]

    print('Path containing test data: "{0}"'.format(regressionPath))
    if os.path.exists(regressionPath) == False:
        print('Error: The above path does not exist. Terminating...')
        return

    print('Path containing executables: "{0}"'.format(execPath))
    if os.path.exists(execPath) == False:
        print('Error: The above path does not exist. Terminating...')
        return
    print('Path to dump all output: "{0}"'.format(outPath))
    if os.path.exists(outPath):
        print('ERROR: The output path "{0}" already exists, please delete or use another path. Terminating...'.format(outPath))
        return

    print('\n')

    # Walking through each separately is slow, so thread (tried this, damn GIL! process spawning didn't make a diff either)
    acsInput = []
    stisInput = []
    wf3Input = []
    if args.cteOnly:
        # acsInput = walkAndFindFiles(regressionPath, 'raw.fits', 'instrume', 'ACS')
        wf3Input = walkAndFindFiles(regressionPath, 'raw.fits', 'instrume', 'WFC3')
    else:
        stisInput = walkAndFindFiles(regressionPath, 'raw.fits', 'instrume', 'STIS')
        acsInput = walkAndFindFiles(regressionPath, 'raw.fits', 'instrume', 'ACS')
        wf3Input = walkAndFindFiles(regressionPath, 'raw.fits', 'instrume', 'WFC3')

    print('{0} acs input files found.'.format(str(len(acsInput))))
    print('{0} stis input files found.'.format(str(len(stisInput))))
    print('{0} wf3 input files found.\n'.format(str(len(wf3Input))))
    print('Time taken to walk directory tree: {0}\n'.format(str(time.time() - startTime)))

    if len(acsInput) == 0 and len(stisInput) == 0 and len(wf3Input) == 0:
        print('No input data files found! Terminating...')
        return

    testQueue = queue.Queue()

    if args.cteOnly:
        print('Processing CTE corrections only.')

        wf3CTEInput = findFilesInList(wf3Input, 'PCTECORR', 'PERFORM')
        print('{0} wf3cte input files found.'.format(str(len(wf3CTEInput))))
        if len(wf3CTEInput) == 0:
            print('Terminating...')
            return

        cmd = os.path.join(execPath, 'wf3cte.e')
        if os.path.exists(cmd) == False:
            # Should this really kill everything or should we continue?
            sys.exit('ERROR: The required executable "{0}" does not exist!'.format(cmd))

        single = True
        for test in wf3CTEInput:
            testItem = TestQueueItem(test, cmd, outPath)
            testQueue.put(testItem)
            if single:
                break

    # else:
    # queue rest of pipeline tests

    # shuffle queue items?

    # Delay doing this such that any failed runs of this code (in adequate paths or zero files found)
    # do not create this directory preventing subsequent attempts due output dir already existing error.
    makeOutputDir(outPath)
    os.chdir(outPath)


    def tester():
        # spin
        while True:
            try:
                test = testQueue.get(timeout=1)
            except queue.Empty:  # only raised when either timeout expires (blocking) or queue empty (nonblocking)
                return
            test.run()
            test.log()
            testQueue.task_done()

    # Create thread pool.
    # Since only using these to run subprocesses.run we don't care about the GIL or
    # that these are threaded rather than multiprocess.
    threadPool = []
    nCores = multiprocessing.cpu_count()
    if args.maxThreads <= 0 or args.maxThreads < nCores:
        nThreads = nCores
    else:
        nThreads = args.maxThreads

    queueLength = testQueue.qsize()
    # Now limit this if greater than items in queue
    if nThreads > queueLength:
        print('Limiting the number of threads to size of queue, {0}, from {1}.'.format(queueLength, nThreads))
        nThreads = queueLength
    print('\nUsing {0} thread(s) to spawn jobs.'.format(nThreads))

    for i in range(nThreads):
        thread = threading.Thread(target=tester)
        thread.start()
        threadPool.append(thread)

    # block until all tasks are done
    testQueue.join()

    # stop threads
    for thread in threadPool:
        thread.join()

    print('\n{0}/{1} tests completed\n'.format(nPassed.get(), queueLength))

    # Move all generated output in regressionPath to outPath/results
    moveTree(regressionPath, os.path.join(outPath, 'results'), ignore=shutil.ignore_patterns('*raw.fits'))
    print('\nTotal time taken: {0}'.format(str(formatSeconds(time.time() - startTime))))

if __name__ == "__main__":
    main(sys.argv[1:])

