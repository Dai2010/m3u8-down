package pkg

import (
	"encoding/json"
	"m3u8-downloader/internal/parser"
	"strings"
)

func ParseM3U8(url, content string) (string, error) {
	pl, err := parser.Parse(strings.NewReader(content))
	if err != nil {
		return "", err
	}
	if idx := strings.LastIndex(url, "/"); idx > 0 {
		parser.ResolveURIs(pl, url[:idx+1])
	}
	b, _ := json.Marshal(pl)
	return string(b), nil
}

func BestStream(playlistJSON string) (string, error) {
	var pl parser.Playlist
	if err := json.Unmarshal([]byte(playlistJSON), &pl); err != nil {
		return "", err
	}
	if pl.IsMaster {
		best := pl.BestStream()
		if best != nil {
			return best.URI, nil
		}
	}
	return "", nil
}

func SelectStream(playlistJSON string, index int) string {
	var pl parser.Playlist
	if err := json.Unmarshal([]byte(playlistJSON), &pl); err != nil {
		return ""
	}
	if index >= 0 && index < len(pl.StreamInfos) {
		return pl.StreamInfos[index].URI
	}
	return ""
}
