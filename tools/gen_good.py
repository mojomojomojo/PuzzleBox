#!/usr/bin/env python3

import sys,os,os.path
import argparse,tempfile,itertools,subprocess,json,datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import parse_maze_comments as analyze


class Leaderboard:
    def __init__(self, keep: int):
        self.keep_count = keep
        self.keep = []

    def add( self, score, *data ):
        self.keep.append((score,data))
        self.keep.sort(reverse=True)
        if len(self.keep) > self.keep_count:
            self.keep = self.keep[:self.keep_count]


def emit(*args,**kwargs):
    if len(args) > 1:
        msg = args[0].format(*(args[1:]))
    else:
        msg = args[0]

    print(msg,**kwargs)
    sys.stdout.flush()

    log_kwargs = kwargs.copy()
    try:
        log_kwargs.pop('file')
    except KeyError:
        pass

    with open('gen_good.log','at',encoding='utf-8') as _log:
        print(msg,**log_kwargs,file=_log)
        

def gen_maze( part, count=100, keep=3, parts=6, leaders=None, *args, **kwargs ):
    if leaders is None:
        leaders = Leaderboard(keep=keep)

    default_kwargs = {
        '--parts':  parts,            # 6 parts, 5 mazes
        '--core-diameter':  15,   # size of empty space in smallest
        '--core-height':  85,     # height of the innermost piece
        '--nubs':  2,             # count of nubs (2,3)
        '--base-height':  8,      # "base height" (mm); the height of the base of the part
        
        '--clearance':  0.4,      # clearance between parts, radius (default: 0.4)

        '--nub-horizontal':  1.0, # scale the size of the nubs
        '--nub-vertical':    1.0,
        '--nub-normal':      1.0,

        '--helix':  0,            # non-helical (no slope to maze path?)
        '--part-thickness':  2,   # wall thickness (mm) (wall of the cylinder, not the maze)
        '--park-thickness':  0.7, # thickness of park ridge to click closed (mm)
        '--maze-thickness':  2,   # maze thickness (mm); the height of the maze walls
        '--maze-complexity':  7, # [-10, +10]
        '--maze-step':  5,        # maze spacing (mm); the (centerline) distance between one cell and the next
        '--maze-margin':  1,      # maze top margin (mm)
        '--outer-sides':  0,      # side count (0: round)
    }
    default_args = [
        '--fix-nubs',
        #'--inside',
    ]

    cmdline_kwargs = default_kwargs.copy()
    for k,v in kwargs.items():
        cmdline_kwargs[k] = v
    cmdline_args = default_args.copy() + list(args)

    cmdline_kwargs['--part'] = part

    puzzlebox_exe = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'../puzzlebox'))

    if part == parts:
        count = 1

    for i in range(count):
        with tempfile.NamedTemporaryFile(suffix='.scad',delete=False) as tmpscad:
            tmpscad.close() # release lock
            command = [ puzzlebox_exe ] + list(map(str,(itertools.chain.from_iterable(cmdline_kwargs.items())))) + cmdline_args + [
                '--out-file', tmpscad.name,
            ]
            
            #print(f'Command: {command}')
            result = subprocess.run(command)
            result.check_returncode()

            with open(tmpscad.name,'rt',encoding='utf-8') as _in:
                scad = _in.read()
            try:
                if part < parts:
                    score,maze,metrics = analyze.score_file(tmpscad.name,weights='')
                    leaders.add(score,i,maze,metrics,scad)
                else:
                    # The last part has no maze, and thus, no score or analysis.
                    leaders.add(1,i,None,{},scad)
            except Exception as e:
                emit(f'Error attempting to score maze.\n#{i} ({tmpscad.name}) part({part}/{parts})\n{command}\n{e}\n{scad}')

            os.remove(tmpscad.name)

    return leaders


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--count',type=int,default=100)
    parser.add_argument('--keep',type=int,default=3)
    parser.add_argument('--part',type=int,default=0)
    cmdline = parser.parse_args()

    kwargs = dict(
        keep = cmdline.keep,
    )

    # puzzlebox assumes the nub count is the same on the inside AND outside
    nubs = { 1:2, 2:2, 3:2, 4:2, 5:3, 6:3 }

    if cmdline.part == 0:
        part_number_range = range(1,7)
    else:
        part_number_range = (cmdline.part,)

    for part_number in part_number_range:
        lead = None
        count = cmdline.count
        if part_number == 6:
            count = 1

        for cplx in (7,10) if part_number < 6 else (7,):
            kwargs['--maze-complexity'] = cplx
            kwargs['--nubs'] = nubs[part_number]
            lead = gen_maze(part=part_number, leaders=lead, count=count, **kwargs)

        lead_index = 0
        for score,info in lead.keep:
            emit(f'\n\n{"=" * 60}')
            lead_index += 1
            idx,maze,metrics,scad = info
            emit(f'Score: {score}')
            if 'human_readable' in metrics:
                emit('\n'.join(metrics['human_readable']['solution']))
            outfile = f'part-{part_number}.{lead_index:02d}.scad'
            with open(outfile, 'wt', encoding='utf-8') as _out:
                print(scad,file=_out)
            emit(outfile)
            with open(f'{outfile}.meta', 'wt', encoding='utf-8') as _out:
                emit(f'Difficulty Score: {score}', file=_out)
                metrics_json = dict(metrics)
                metrics_json.pop('human_readable', None)
                emit(json.dumps(metrics_json, indent=2),file=_out)
                if 'human_readable' in metrics:
                    emit(f'\n\n{"\n".join(metrics["human_readable"]["visualization"])}',file=_out)
                    emit(f'\n\n{"\n".join(metrics["human_readable"]["solution"])}',file=_out)

            emit('\nGenerating STL')
            started = datetime.datetime.now()
            result = subprocess.run([ 'openscad', '-q', outfile, '-o', f'{outfile}.stl'])
            elapsed = datetime.datetime.now() - started
            emit(f'  {outfile}.stl: {elapsed}')
