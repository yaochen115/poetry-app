import 'package:flutter/material.dart';

import '../simplified_chinese.dart';
import '../state.dart';
import '../theme.dart';

/// 长按查字典的底部词典卡。
Future<void> showDictSheet(
  BuildContext context,
  DictionaryResult result, {
  SimplifiedChinese? simplifiedChinese,
}) {
  if (simplifiedChinese != null) {
    final attribution = result.attribution.replaceFirst(
      '釋義與例證保留原文，僅轉換資料格式並建立查詢索引。',
      '源库保留原文，本页显示简体。',
    );
    result = DictionaryResult(
      head: simplifiedChinese.convert(result.head),
      pinyin: result.pinyin,
      meanings: result.meanings.map(simplifiedChinese.convert).toList(),
      isWord: result.isWord,
      attribution: simplifiedChinese.convert(attribution),
    );
  }
  return showModalBottomSheet(
    context: context,
    backgroundColor: HzColors.of(context).card,
    barrierColor: const Color(0x40201D18),
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
    ),
    builder: (ctx) => SingleChildScrollView(child: _DictSheet(result: result)),
  );
}

class _DictSheet extends StatelessWidget {
  final DictionaryResult result;
  const _DictSheet({required this.result});

  @override
  Widget build(BuildContext context) {
    final single = result.head.runes.length == 1;
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(24, 22, 24, 26),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(
                  result.head,
                  style: TextStyle(
                    fontSize: single ? 40 : 30,
                    fontWeight: FontWeight.w600,
                    height: 1.2,
                    color: HzColors.of(context).ink,
                  ),
                ),
                if (result.pinyin.isNotEmpty) ...[
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      result.pinyin,
                      style: TextStyle(
                        fontSize: 15,
                        color: HzColors.of(context).seal,
                        letterSpacing: 1,
                      ),
                    ),
                  ),
                ],
              ],
            ),
            const SizedBox(height: 12),
            Text(
              '字词释义',
              style: TextStyle(
                fontSize: 12,
                color: HzColors.of(context).ink2,
                letterSpacing: 1,
              ),
            ),
            const SizedBox(height: 6),
            ...result.meanings.map(
              (m) => Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text(
                  m,
                  style: TextStyle(
                    fontSize: 14.5,
                    height: 1.9,
                    color: HzColors.of(context).ink,
                  ),
                ),
              ),
            ),
            if (result.attribution.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text(result.attribution,
                  style: TextStyle(fontSize: 11, height: 1.5,
                      color: HzColors.of(context).ink2)),
            ],
          ],
        ),
      ),
    );
  }
}
