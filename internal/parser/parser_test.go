package parser

import (
	"strings"
	"testing"
)

func TestParseVOD(t *testing.T) {
	raw := `#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:10
#EXT-X-MEDIA-SEQUENCE:0
#EXT-X-PLAYLIST-TYPE:VOD
#EXTINF:10.000,
segment-0.ts
#EXTINF:10.000,
segment-1.ts
#EXTINF:10.000,
segment-2.ts
#EXT-X-ENDLIST`

	pl, err := Parse(strings.NewReader(raw))
	if err != nil {
		t.Fatal(err)
	}

	if pl.Version != 3 {
		t.Errorf("version = %d, want 3", pl.Version)
	}
	if pl.TargetDuration != 10 {
		t.Errorf("targetDuration = %f, want 10", pl.TargetDuration)
	}
	if pl.PlaylistType != "VOD" {
		t.Errorf("playlistType = %s, want VOD", pl.PlaylistType)
	}
	if !pl.Endlist {
		t.Error("expected endlist")
	}
	if len(pl.Segments) != 3 {
		t.Fatalf("got %d segments, want 3", len(pl.Segments))
	}

	tests := []struct {
		uri      string
		duration float64
		seq      int
	}{
		{"segment-0.ts", 10, 0},
		{"segment-1.ts", 10, 1},
		{"segment-2.ts", 10, 2},
	}

	for i, tt := range tests {
		seg := pl.Segments[i]
		if seg.URI != tt.uri {
			t.Errorf("seg[%d] URI = %s, want %s", i, seg.URI, tt.uri)
		}
		if seg.Duration != tt.duration {
			t.Errorf("seg[%d] duration = %f, want %f", i, seg.Duration, tt.duration)
		}
		if seg.Sequence != tt.seq {
			t.Errorf("seg[%d] sequence = %d, want %d", i, seg.Sequence, tt.seq)
		}
	}
}

func TestParseWithKey(t *testing.T) {
	raw := `#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:10
#EXT-X-KEY:METHOD=AES-128,URI="https://example.com/key",IV=0x1234567890abcdef
#EXTINF:10.000,
seg-0.ts
#EXTINF:10.000,
seg-1.ts
#EXT-X-ENDLIST`

	pl, err := Parse(strings.NewReader(raw))
	if err != nil {
		t.Fatal(err)
	}

	if len(pl.Segments) != 2 {
		t.Fatalf("got %d segments", len(pl.Segments))
	}

	for i, seg := range pl.Segments {
		if seg.Key == nil {
			t.Fatalf("seg[%d] key is nil", i)
		}
		if seg.Key.Method != "AES-128" {
			t.Errorf("seg[%d] key method = %s", i, seg.Key.Method)
		}
		if seg.Key.URI != "https://example.com/key" {
			t.Errorf("seg[%d] key URI = %s", i, seg.Key.URI)
		}
		if seg.Key.IV != "0x1234567890abcdef" {
			t.Errorf("seg[%d] key IV = %s", i, seg.Key.IV)
		}
	}
}

func TestParseMasterPlaylist(t *testing.T) {
	raw := `#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=1280000,AVERAGE-BANDWIDTH=1000000,CODECS="avc1.64001e,mp4a.40.2",RESOLUTION=1280x720,FRAME-RATE=30.000
high.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=640000,AVERAGE-BANDWIDTH=500000,CODECS="avc1.64001e,mp4a.40.2",RESOLUTION=854x480
medium.m3u8
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio-stereo",NAME="English",LANGUAGE="en",DEFAULT=YES,AUTO-SELECT=YES,URI="audio/en.m3u8"`

	pl, err := Parse(strings.NewReader(raw))
	if err != nil {
		t.Fatal(err)
	}

	if !pl.IsMaster {
		t.Error("expected master playlist")
	}
	if len(pl.StreamInfos) != 2 {
		t.Fatalf("got %d streams, want 2", len(pl.StreamInfos))
	}
	if pl.StreamInfos[0].Bandwidth != 1280000 {
		t.Errorf("bandwidth = %d, want 1280000", pl.StreamInfos[0].Bandwidth)
	}
	if pl.StreamInfos[0].Resolution != "1280x720" {
		t.Errorf("resolution = %s", pl.StreamInfos[0].Resolution)
	}
	if pl.StreamInfos[0].URI != "high.m3u8" {
		t.Errorf("URI = %s", pl.StreamInfos[0].URI)
	}

	if len(pl.MediaInfos) != 1 {
		t.Fatalf("got %d media infos, want 1", len(pl.MediaInfos))
	}
	if pl.MediaInfos[0].Type != "AUDIO" {
		t.Errorf("media type = %s", pl.MediaInfos[0].Type)
	}
	if !pl.MediaInfos[0].Default {
		t.Error("expected default=true")
	}
}

func TestParseLivePlaylist(t *testing.T) {
	raw := `#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:8
#EXT-X-MEDIA-SEQUENCE:2680
#EXTINF:8.000,
segment-2680.ts
#EXTINF:8.000,
segment-2681.ts
#EXTINF:8.000,
segment-2682.ts`

	pl, err := Parse(strings.NewReader(raw))
	if err != nil {
		t.Fatal(err)
	}

	if pl.Endlist {
		t.Error("live playlist should not have endlist")
	}
	if pl.MediaSequence != 2680 {
		t.Errorf("mediaSequence = %d", pl.MediaSequence)
	}
	if len(pl.Segments) != 3 {
		t.Fatalf("got %d segments", len(pl.Segments))
	}
	if pl.Segments[0].Sequence != 2680 {
		t.Errorf("seq = %d, want 2680", pl.Segments[0].Sequence)
	}
}

func TestParseDiscontinuity(t *testing.T) {
	raw := `#EXTM3U
#EXT-X-VERSION:3
#EXTINF:10.000,
seg-0.ts
#EXT-X-DISCONTINUITY
#EXTINF:10.000,
seg-1.ts
#EXTINF:10.000,
seg-2.ts
#EXT-X-ENDLIST`

	pl, err := Parse(strings.NewReader(raw))
	if err != nil {
		t.Fatal(err)
	}

	if pl.Segments[0].Discontinuity {
		t.Error("seg[0] should not have discontinuity")
	}
	if !pl.Segments[1].Discontinuity {
		t.Error("seg[1] should have discontinuity")
	}
	if pl.Segments[2].Discontinuity {
		t.Error("seg[2] should not have discontinuity")
	}
}

func TestResolveURIs(t *testing.T) {
	raw := `#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:10
#EXT-X-KEY:METHOD=AES-128,URI="key.bin"
#EXTINF:10.000,
seg-0.ts
#EXTINF:10.000,
seg-1.ts
#EXT-X-ENDLIST`

	pl, err := Parse(strings.NewReader(raw))
	if err != nil {
		t.Fatal(err)
	}

	err = ResolveURIs(pl, "https://example.com/hls/video.m3u8")
	if err != nil {
		t.Fatal(err)
	}

	if pl.Segments[0].URI != "https://example.com/hls/seg-0.ts" {
		t.Errorf("resolved URI = %s", pl.Segments[0].URI)
	}
	if pl.Segments[0].Key.URI != "https://example.com/hls/key.bin" {
		t.Errorf("resolved key URI = %s", pl.Segments[0].Key.URI)
	}
}

func TestBestStream(t *testing.T) {
	raw := `#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=640000,RESOLUTION=854x480
medium.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=1280000,RESOLUTION=1280x720
high.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=256000,RESOLUTION=426x240
low.m3u8`

	pl, err := Parse(strings.NewReader(raw))
	if err != nil {
		t.Fatal(err)
	}

	best := pl.BestStream()
	if best == nil {
		t.Fatal("best stream is nil")
	}
	if best.Bandwidth != 1280000 {
		t.Errorf("best bandwidth = %d, want 1280000", best.Bandwidth)
	}
}

func TestTotalDuration(t *testing.T) {
	raw := `#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:10
#EXTINF:9.900,
seg-0.ts
#EXTINF:10.050,
seg-1.ts
#EXTINF:9.800,
seg-2.ts
#EXT-X-ENDLIST`

	pl, err := Parse(strings.NewReader(raw))
	if err != nil {
		t.Fatal(err)
	}

	total := pl.TotalDuration()
	expected := 9.9 + 10.05 + 9.8
	diff := total - expected
	if diff < 0 {
		diff = -diff
	}
	if diff > 0.0001 {
		t.Errorf("total = %f, want %f", total, expected)
	}
}
