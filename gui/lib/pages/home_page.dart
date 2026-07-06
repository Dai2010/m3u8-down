import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final _urlController = TextEditingController();
  bool _loading = false;
  String? _error;
  Map<String, dynamic>? _playlist;

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  Future<void> _parse() async {
    final url = _urlController.text.trim();
    if (url.isEmpty) return;

    setState(() {
      _loading = true;
      _error = null;
      _playlist = null;
    });

    try {
      final httpClient = HttpClient();
      final request = await httpClient.getUrl(Uri.parse(url));
      request.headers.set('User-Agent', 'Mozilla/5.0');
      final response = await request.close();
      final content = await response.transform(utf8.decoder).join();

      // TODO: call Go engine via FFI
      setState(() {
        _playlist = {
          'segments': 128,
          'duration': 1290.0,
          'title': content.substring(0, content.length.clamp(0, 50)),
        };
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('M3U8 Down'),
        centerTitle: true,
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    TextField(
                      controller: _urlController,
                      decoration: const InputDecoration(
                        labelText: 'M3U8 链接',
                        hintText: 'https://example.com/video.m3u8',
                        prefixIcon: Icon(Icons.link),
                        border: OutlineInputBorder(),
                      ),
                      textInputAction: TextInputAction.go,
                      onSubmitted: (_) => _parse(),
                    ),
                    const SizedBox(height: 12),
                    FilledButton.icon(
                      onPressed: _loading ? null : _parse,
                      icon: _loading
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Icon(Icons.play_arrow),
                      label: Text(_loading ? '解析中...' : '解析'),
                    ),
                  ],
                ),
              ),
            ),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Card(
                  color: theme.colorScheme.errorContainer,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      children: [
                        Icon(Icons.error_outline,
                            color: theme.colorScheme.error),
                        const SizedBox(width: 8),
                        Expanded(child: Text(_error!)),
                      ],
                    ),
                  ),
                ),
              ),
            if (_playlist != null) ...[
              const SizedBox(height: 16),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('解析结果',
                          style: theme.textTheme.titleMedium),
                      const Divider(),
                      _infoRow('片段数', '${_playlist!['segments']}'),
                      _infoRow('总时长',
                          '${((_playlist!['duration'] as num) / 60).toStringAsFixed(1)} 分钟'),
                      _infoRow('标题', _playlist!['title'] as String),
                      const SizedBox(height: 12),
                      FilledButton.icon(
                        onPressed: () {},
                        icon: const Icon(Icons.download),
                        label: const Text('开始下载'),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _infoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          SizedBox(
            width: 80,
            child: Text(label,
                style: const TextStyle(fontWeight: FontWeight.w500)),
          ),
          Expanded(child: Text(value)),
        ],
      ),
    );
  }
}
