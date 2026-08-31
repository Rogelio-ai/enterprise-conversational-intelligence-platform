from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
import sys

from . import PROTOCOL_VERSION, __version__
from .adapters import CupsAdapter
from .cloud import CloudClient
from .config import load_config, load_credentials
from .ledger import Ledger
from .runtime import ConnectorRuntime, singleton_lock


DEFAULT_CONFIG = '/etc/pryecip-local-connector/config.toml'


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='pryecip-local-connector')
    parser.add_argument('--config', default=DEFAULT_CONFIG)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('run')
    commands.add_parser('status')
    return parser


def main() -> None:
    args = _parser().parse_args()
    config = load_config(args.config)
    if args.command == 'status':
        ledger = Ledger(config.ledger_path)
        try:
            queue_info: tuple[str, ...] | str
            try:
                queue_info = CupsAdapter().queues()
            except Exception:
                queue_info = 'unavailable'
            print(json.dumps({
                'connector_version': __version__,
                'protocol_version': PROTOCOL_VERSION,
                'credentials_present': config.credentials_path.is_file(),
                'ledger_integrity': ledger.integrity_check(),
                'backlog_count': ledger.backlog_count(),
                'configured_targets': sorted(config.targets),
                'cups_queues': queue_info,
            }, ensure_ascii=False, sort_keys=True))
        finally:
            ledger.close()
        return
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
    )
    lock_path = config.ledger_path.with_suffix(config.ledger_path.suffix + '.lock')
    with singleton_lock(lock_path):
        ledger = Ledger(config.ledger_path)
        try:
            if not ledger.integrity_check():
                raise RuntimeError('SQLite ledger integrity check failed')
            credentials = load_credentials(config.credentials_path)
            cloud = CloudClient(config, credentials)
            runtime = ConnectorRuntime(config, ledger, cloud)
            try:
                asyncio.run(runtime.run_forever())
            finally:
                cloud.close()
        finally:
            ledger.close()


if __name__ == '__main__':
    main()
