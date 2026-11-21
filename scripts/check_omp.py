#!/usr/bin/env python3
"""Exercise generated plugin loading, manual invocation, and path-gated rules in OMP.

The scope checks use the configured model; assertions inspect runtime events, not prose.
"""
import argparse
import json
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


def rpc(args, cwd, requests, finished):
    process = subprocess.Popen(args, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    incoming, errors, events = queue.Queue(), [], []

    def receive():
        for line in process.stdout:
            incoming.put(json.loads(line))
        incoming.put(None)

    reader = threading.Thread(target=receive, daemon=True)
    error_reader = threading.Thread(target=lambda: errors.append(process.stderr.read()), daemon=True)
    reader.start()
    error_reader.start()
    deadline = time.monotonic() + 180
    try:
        while True:
            event = incoming.get(timeout=max(0.01, deadline - time.monotonic()))
            if event is None:
                raise RuntimeError(f"OMP exited before verification completed: {''.join(errors)}")
            events.append(event)
            if event['type'] == 'ready':
                for request in requests:
                    process.stdin.write(json.dumps(request) + '\n')
                process.stdin.flush()
            if finished(events):
                if any(request['type'] == 'prompt' for request in requests):
                    process.stdin.write('{"id":"stop","type":"abort"}\n')
                    process.stdin.flush()
                return events
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        reader.join(timeout=5)
        error_reader.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', help='OMP profile with an authenticated model')
    options = parser.parse_args()
    args = ['omp', '--plugin-dir', str(ROOT / 'omp'), '--mode', 'rpc', '--no-session',
            '--no-extensions', '--no-context-files', '--no-title', '--no-lsp', '--no-pty']
    if options.profile:
        args += ['--profile', options.profile]
    with tempfile.TemporaryDirectory(prefix='om-pstack-runtime-') as directory:
        events = rpc(args, directory, [
            {'id': 'commands', 'type': 'get_available_commands'},
            {'id': 'state', 'type': 'get_state'},
        ], lambda es: sum(e['type'] == 'response' for e in es) == 2)
        responses = {e['id']: e['data'] for e in events if e['type'] == 'response'}
        expected = {p.parent.name for p in (ROOT / 'omp/skills').glob('*/SKILL.md')}
        registered = {c['name'].removeprefix('skill:') for c in responses['commands']['commands']}
        assert expected <= registered, expected - registered
        prompt = '\n'.join(responses['state']['systemPrompt'])
        catalog = prompt.split('<skills>', 1)[1].split('</skills>', 1)[0]
        listed = {line.split(':', 1)[0][2:] for line in catalog.splitlines() if line.startswith('- ')}
        assert expected & listed == {'setup-pstack'}, expected & listed
        tools = json.dumps(responses['state']['dumpTools'])
        assert all(name in tools for name in ('poteto-agent', 'comment-sicko'))
        events = rpc(args, directory, [{'id': 'invoke', 'type': 'prompt', 'message': '/skill:poteto-help CHECK'}],
                     lambda es: any(e['type'] == 'message_start' for e in es))
        invocation = next(e['message'] for e in events if e['type'] == 'message_start')
        assert invocation.get('customType') == 'skill-prompt', invocation
        assert 'User: CHECK' in str(invocation['content']), invocation
        assert '/skill:poteto-mode' in str(invocation['content']), invocation
        for extension in ('py', 'ts', 'tsx'):
            Path(directory, f'scope.{extension}').write_text('scope = 1\n')
            events = rpc(args + ['--tools', 'read'], directory, [{
                'id': 'scope', 'type': 'prompt',
                'message': f'Verification only. Read scope.{extension} with the read tool. '
                           'Follow runtime rules. Do not edit files or run commands. Finish after this read.',
            }], lambda es: any(e['type'] == 'session_settled' for e in es))
            triggers = [i for i, e in enumerate(events) if e['type'] == 'ttsr_triggered'
                        and any(r['name'] == 'typescript-best-practices' for r in e['rules'])]
            file_read = next(i for i, e in enumerate(events) if e['type'] == 'tool_execution_end'
                             and not e.get('isError')
                             and e.get('result', {}).get('details', {}).get('meta', {}).get('source', {}).get('value')
                             == str(Path(directory, f'scope.{extension}')))
            if extension == 'py':
                assert not triggers, triggers
            else:
                skill_read = next(i for i, e in enumerate(events) if e['type'] == 'tool_execution_start'
                                  and e.get('args', {}).get('path') == 'skill://typescript-best-practices')
                assert triggers and triggers[0] < skill_read < file_read, (extension, triggers, skill_read, file_read)
                errors = [e for e in events if e['type'] == 'tool_execution_end' and e.get('isError')]
                assert not errors, errors
                principle_read = next(i for i, e in enumerate(events) if e['type'] == 'tool_execution_end'
                                      and not e.get('isError')
                                      and e.get('result', {}).get('details', {}).get('meta', {}).get('source', {}).get('value')
                                      == str(ROOT / 'omp/skills/principle-type-system-discipline/SKILL.md'))
                assert skill_read < principle_read < file_read, (extension, skill_read, principle_read, file_read)
    print(f'OMP runtime verified: {len(expected)} skills, native command references, manual visibility/invocation, '
          '2 agents, TS/TSX scope and resolved principle reads without tool errors; Python excluded.')


if __name__ == '__main__':
    main()
