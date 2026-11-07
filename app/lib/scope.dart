import 'package:flutter/material.dart';

import 'state.dart';

/// 通过 InheritedNotifier 向下传递 AppState，状态变化时依赖方自动重建。
class StateScope extends InheritedNotifier<AppState> {
  const StateScope({
    super.key,
    required AppState state,
    required super.child,
  }) : super(notifier: state);

  static AppState of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<StateScope>();
    assert(scope != null, 'StateScope not found in widget tree');
    return scope!.notifier!;
  }

  static AppState read(BuildContext context) {
    final scope = context.getInheritedWidgetOfExactType<StateScope>();
    assert(scope != null, 'StateScope not found in widget tree');
    return scope!.notifier!;
  }
}
