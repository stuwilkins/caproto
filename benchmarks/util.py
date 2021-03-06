import os
import subprocess
import shutil
import time
from contextlib import contextmanager
from tempfile import NamedTemporaryFile


def find_dbd_path():
    '''Find the path to database definitions, based on the environment'''
    if 'EPICS_BASE' in os.environ:
        return os.path.join(os.environ['EPICS_BASE'], 'dbd')
    else:
        softioc_path = shutil.which('softIoc')
        return os.path.abspath(os.path.join(softioc_path, '..', '..', 'dbd'))


@contextmanager
def softioc(*, db_text='', access_rules_text='', additional_args=None,
            macros=None, dbd_path=None, dbd_name='softIoc.dbd', env=None):
    '''[context manager] Start a soft IOC on-demand

    Parameters
    ----------
    db_text : str
        Database text
    access_rules_text : str
        Access security group text, optional
    additional_args : list
        List of additional args to pass to softIoc
    macros : dict
        Dictionary of key to value
    dbd_path : str, optional
        Path to dbd directory
        Uses `find_dbd_path()` if None
    dbd_name : str
        Name of dbd file
    env : dict
        Environment variables to pass

    Yields
    ------
    proc : subprocess.Process
    '''
    if not access_rules_text:
        access_rules_text = '''
            ASG(DEFAULT) {
                RULE(1,READ)
                RULE(1,WRITE,TRAPWRITE)
            }
            '''

    if additional_args is None:
        additional_args = []

    if macros is None:
        macros = dict(P='test')

    proc_env = dict(os.environ)
    if env is not None:
        proc_env.update(**env)

    # if 'EPICS_' not in proc_env:

    macros = ','.join('{}={}'.format(k, v) for k, v in macros.items())

    with NamedTemporaryFile(mode='w+') as cf:
        cf.write(access_rules_text)
        cf.flush()

        with NamedTemporaryFile(mode='w+') as df:
            df.write(db_text)
            df.flush()

            if dbd_path is None:
                dbd_path = find_dbd_path()

            dbd_path = os.path.join(dbd_path, dbd_name)
            assert os.path.exists(dbd_path)

            popen_args = ['softIoc',
                          '-D', dbd_path,
                          '-m', macros,
                          '-a', cf.name,
                          '-d', df.name]
            proc = subprocess.Popen(popen_args + additional_args, env=proc_env,
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE)
            yield proc

            proc.kill()
            proc.wait()


def make_database(records):
    '''Make an EPICS database from a dictionary of records

    Parameters
    ----------
    records : dict
        Keys: ('record_name', 'record_type')
        Values: dictionary of {'field': 'field_value'}

    Returns
    -------
    Newline-delimited block of text
    '''

    def gen():
        for (record, rtyp), field_info in records.items():
            yield 'record({}, "{}")'.format(rtyp, record)
            yield '{'

            for field_name, field_value in field_info.items():
                yield '    field({}, "{}")'.format(field_name, field_value)
            yield '}'
            yield ''

    return '\n'.join(gen())


def _main():
    # simple test
    test_db = make_database(
        {('$(P):bo', 'bo'): dict(ZNAM='OUT', ONAM='IN'),
         ('$(P):ao', 'ao'): dict(DRVH=5, DRVL=1),
         },
    )
    with softioc(db_text=test_db):
        time.sleep(5)


@contextmanager
def timer():
    '''Timing context manager

    Yields
    ------
    tr : TimeResults
        with attributes t0, t1, elapsed
    '''
    class TimeResults:
        t0 = None
        t1 = None
        elapsed = None

    tr = TimeResults()
    tr.t0 = time.time()

    try:
        yield tr
    finally:
        tr.t1 = time.time()
        tr.elapsed = tr.t1 - tr.t0

if __name__ == '__main__':
    _main()
