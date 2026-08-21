# -*- coding: utf-8 -*-
"""Precompute the structural profile of the retail Japanese DS script.

Two guards in inject.py need to compare against the JAPANESE original rather than
the fan patch (see the README, "Aligning to the right reference"). Neither needs
the Japanese *text* - only counts:

  boxes  per string, how many message-box terminators it contains. The fan patch
         redistributed boxes between strings in 54 entries; a string whose count
         differs from the JP original cannot safely take official text.
  ctrl   per entry, a histogram of control codes. A wrong file match shows up as
         near-zero overlap against this.

Both are integers - facts about the file's structure, not its content - so they
can ship with the tool. That removes the retail Japanese ROM from the list of
things a user has to supply.

Regenerate after extracting a JP ROM:
    python tools/jp_profile.py dump/ds_jp/jpn/spt.bin dump/jp_structure.json
"""
import sys, os, json, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from map_ids import ds_entries
from spt import all_strings

BOXEND = {0xE102, 0xE104, 0xE106, 0xE185, 0xE081}


def profile(spt_path):
    out = {}
    for i, entry in ds_entries(spt_path):
        try:
            strings = list(all_strings(entry, True))
        except Exception:
            continue
        boxes, ctrl = [], collections.Counter()
        for _, _, _, u in strings:
            boxes.append(sum(1 for v in u if v in BOXEND))
            ctrl.update(v for v in u if 0xE000 <= v <= 0xF8FF)
        out[str(i)] = {'boxes': boxes,
                       'ctrl': {'%04X' % k: v for k, v in sorted(ctrl.items())}}
    return out


if __name__ == '__main__':
    src = sys.argv[1] if len(sys.argv) > 1 else 'dump/ds_jp/jpn/spt.bin'
    dst = sys.argv[2] if len(sys.argv) > 2 else 'dump/jp_structure.json'
    p = profile(src)
    with open(dst, 'w') as f:
        json.dump(p, f, separators=(',', ':'), sort_keys=True)
    print('%d entries -> %s (%.0f KB)' % (len(p), dst, os.path.getsize(dst) / 1024))
