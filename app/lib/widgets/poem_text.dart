import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../format.dart';
import '../theme.dart';

/// 网格排版的诗词正文。
///
/// - 以不可见的格子为单位：每个汉字占一格；连续标点（如「：」）合并为一格；
/// - 行尾标点「悬挂」到格子最右侧之外（宽度为 0，向右溢出）；
/// - 古诗居中时不考虑末尾句号宽度；
/// - 每「逻辑行」用一个 Wrap，长行自动换行；每个汉字挂长按手势（词优先查字典）。
class PoemText extends StatefulWidget {
  final String content;
  final String category;
  final double fontSize;
  final double lineHeight;
  final double letterSpacing;
  final bool center;
  final void Function(String ch, String prev, String next)? onLongPress;

  const PoemText({
    super.key,
    required this.content,
    required this.category,
    this.fontSize = 20,
    this.lineHeight = 2.0,
    this.letterSpacing = 2.0,
    this.center = false,
    this.onLongPress,
  });

  @override
  State<PoemText> createState() => _PoemTextState();
}

/// 一行中的一个格子：正文汉字 / 连续标点 / 缩进空格。
class _Cell {
  final String text;
  final bool isPunct; // 连续标点合并为一格
  final bool isSpace; // 全角空格（缩进）
  final bool isHanzi; // 可查字典的汉字格
  const _Cell(
    this.text, {
    this.isPunct = false,
    this.isSpace = false,
    this.isHanzi = false,
  });
}

class _PoemTextState extends State<PoemText> {
  final List<LongPressGestureRecognizer> _recs = [];
  late final List<List<_Cell>> _lines;
  late final List<_Cell> _hanziCells; // 全部可查字，按顺序，用于前后相邻

  @override
  void initState() {
    super.initState();
    final formatted = formatBody(widget.category, widget.content);
    _lines = _tokenize(formatted);
    _hanziCells = [for (final ln in _lines) ...ln.where((c) => c.isHanzi)];
  }

  List<List<_Cell>> _tokenize(String formatted) {
    final out = <List<_Cell>>[];
    for (final line in formatted.split('\n')) {
      final cells = <_Cell>[];
      final cps = line.runes.toList();
      var i = 0;
      while (i < cps.length) {
        final cp = cps[i];
        final ch = String.fromCharCode(cp);
        if (isSpace(ch)) {
          cells.add(_Cell(ch, isSpace: true));
          i++;
          continue;
        }
        if (_isPunct(cp)) {
          // 连续标点合并为一格
          var buf = ch;
          var j = i + 1;
          while (j < cps.length && _isPunct(cps[j])) {
            buf += String.fromCharCode(cps[j]);
            j++;
          }
          cells.add(_Cell(buf, isPunct: true));
          i = j;
          continue;
        }
        // 汉字（或其它字符）单字一格
        cells.add(_Cell(ch, isHanzi: true));
        i++;
      }
      out.add(cells);
    }
    return out;
  }

  bool _isPunct(int cp) {
    return (cp >= 0x3001 && cp <= 0x303F) ||
        (cp >= 0xFF00 && cp <= 0xFF0F) ||
        (cp >= 0xFF1A && cp <= 0xFF1F) ||
        cp == 0x2018 ||
        cp == 0x2019 ||
        cp == 0x201C ||
        cp == 0x201D ||
        cp == 0x2026 ||
        cp == 0x2014 ||
        cp == 0x2013 ||
        cp == 0x27;
  }

  LongPressGestureRecognizer _recognizerFor(int index) {
    final rec = LongPressGestureRecognizer(
      duration: const Duration(milliseconds: 480),
    );
    rec.onLongPressStart = (_) {
      HapticFeedback.mediumImpact();
      final cell = _hanziCells[index];
      final prev = index > 0 ? _hanziCells[index - 1].text : '';
      final next = index < _hanziCells.length - 1
          ? _hanziCells[index + 1].text
          : '';
      widget.onLongPress?.call(cell.text, prev, next);
    };
    return rec;
  }

  @override
  void dispose() {
    for (final r in _recs) {
      r.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final maxW = constraints.maxWidth;
        var fontSize = widget.fontSize;
        var cellW = widget.fontSize + widget.letterSpacing;
        if (widget.center) {
          // 古诗：整行必须放得下，按最长行自动缩字号，保证不把一句折到两行。
          var maxCells = 0;
          for (final line in _lines) {
            if (line.length > maxCells) maxCells = line.length;
          }
          if (maxCells > 0 && maxW.isFinite) {
            final fitted = (maxW - 2) / maxCells;
            if (fitted < cellW) {
              fontSize = (fitted - widget.letterSpacing)
                  .clamp(10.0, widget.fontSize)
                  .toDouble();
              cellW = fontSize + widget.letterSpacing;
            }
          }
        }
        final rowH = fontSize * widget.lineHeight;
        final textStyle = TextStyle(
          fontSize: fontSize,
          color: HzColors.of(context).ink,
          height: 1.0,
        );

        final lineWidgets = <Widget>[];
        var hzIdx = 0;
        for (final line in _lines) {
          final children = <Widget>[];
          for (var i = 0; i < line.length; i++) {
            final cell = line[i];
            final trailingPunct = cell.isPunct && i == line.length - 1;
            if (trailingPunct) {
              // 行尾标点：宽度 0，向右溢出悬挂，不计入居中宽度。
              children.add(
                SizedBox(
                  width: 0,
                  height: rowH,
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      cell.text,
                      style: textStyle,
                      softWrap: false,
                      overflow: TextOverflow.visible,
                    ),
                  ),
                ),
              );
            } else if (cell.isSpace) {
              children.add(_plainCell(cellW, rowH, '', textStyle));
            } else if (cell.isPunct) {
              children.add(_plainCell(cellW, rowH, cell.text, textStyle));
            } else {
              // 汉字格：挂长按手势。
              final rec = _recognizerFor(hzIdx);
              _recs.add(rec);
              hzIdx++;
              children.add(
                SizedBox(
                  width: cellW,
                  height: rowH,
                  child: Center(
                    child: Text.rich(
                      TextSpan(text: cell.text, recognizer: rec),
                      style: textStyle,
                    ),
                  ),
                ),
              );
            }
          }
          lineWidgets.add(
            Wrap(
              alignment: widget.center
                  ? WrapAlignment.center
                  : WrapAlignment.start,
              spacing: 0,
              runSpacing: 0,
              children: children,
            ),
          );
        }

        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: lineWidgets,
        );
      },
    );
  }

  Widget _plainCell(double w, double h, String text, TextStyle style) {
    return SizedBox(
      width: w,
      height: h,
      child: Center(
        child: Text(
          text,
          style: style,
          softWrap: false,
          overflow: TextOverflow.visible,
        ),
      ),
    );
  }
}
