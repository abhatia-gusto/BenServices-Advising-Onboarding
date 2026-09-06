import subprocess, sys, os, json
QTAG='{"qtag":{"version":"1.1.0","source":{"claude_code":{"username":"claude","hostname":"nice-amazing-gates","source":"query-snowflake-skill"}}}}'
def run(sql_file, out_json):
    sql=open(sql_file).read()
    full="ALTER SESSION SET QUERY_TAG = '%s';\n%s"%(QTAG, sql)
    env=dict(os.environ); env['PATH']=os.path.expanduser('~/.local/bin')+':'+env.get('PATH','')
    r=subprocess.run(['snow','sql','-q',full,'--enable-templating','NONE','--format','JSON'],capture_output=True,text=True,env=env)
    if r.returncode!=0:
        sys.stderr.write(r.stderr[-1500:]); sys.exit(1)
    data=json.loads(r.stdout.strip())
    # multi-statement: list of per-statement result lists. take last list of dict rows.
    rows=data
    if isinstance(data,list) and data and isinstance(data[-1],list):
        rows=data[-1]
    json.dump(rows, open(out_json,'w'))
    print("OK %d rows -> %s"%(len(rows), out_json))
    return rows
if __name__=='__main__':
    run(sys.argv[1], sys.argv[2])
