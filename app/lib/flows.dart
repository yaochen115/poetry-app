import 'package:flutter/material.dart';

import 'state.dart';
import 'widgets/pick_sheet.dart';

/// 标记掌握度流程：设置掌握度 → 弹出四选一（不再弹「已标记」提示）。
void markPoem(BuildContext context, AppState state, String id, int v) {
  state.setMastery(id, v);
  showPickSheet(context, state);
}
