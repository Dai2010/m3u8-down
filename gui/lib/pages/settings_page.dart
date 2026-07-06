import 'package:flutter/material.dart';

class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('设置'),
        centerTitle: true,
      ),
      body: ListView(
        children: [
          _section(theme, '下载'),
          _tile(Icons.tune, '并发线程数', '4', theme),
          _tile(Icons.folder_outlined, '保存路径', '/下载', theme),
          _tile(Icons.replay, '重试次数', '3', theme),
          _tile(Icons.timer_outlined, '超时（秒）', '30', theme),
          _divider(),
          _section(theme, '网络'),
          _tile(Icons.shield_outlined, '代理', '未设置', theme),
          _tile(Icons.vpn_key_outlined, '自定义 Headers', '', theme),
          _divider(),
          _section(theme, '广告过滤'),
          _tile(Icons.filter_alt_outlined, '过滤关键词', '未设置', theme),
          _divider(),
          _section(theme, '关于'),
          _tile(Icons.info_outline, '版本', '1.0.0', theme),
        ],
      ),
    );
  }

  Widget _divider() => const Divider(height: 1);

  Widget _section(ThemeData theme, String title) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
      child: Text(title,
          style: theme.textTheme.titleSmall?.copyWith(
            color: theme.colorScheme.primary,
          )),
    );
  }

  Widget _tile(IconData icon, String title, String subtitle, ThemeData theme) {
    return ListTile(
      leading: Icon(icon),
      title: Text(title),
      trailing: Text(subtitle,
          style: TextStyle(color: theme.colorScheme.outline)),
      onTap: () {},
    );
  }
}
