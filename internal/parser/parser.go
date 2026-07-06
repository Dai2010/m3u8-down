package parser

import (
	"fmt"
	"io"
	"net/url"
	"path"
	"strconv"
	"strings"
)

func Parse(r io.Reader) (*Playlist, error) {
	data, err := io.ReadAll(r)
	if err != nil {
		return nil, fmt.Errorf("read failed: %w", err)
	}

	pl := &Playlist{}
	lines := strings.Split(strings.ReplaceAll(string(data), "\r\n", "\n"), "\n")

	if len(lines) == 0 || strings.TrimSpace(lines[0]) != "#EXTM3U" {
		return nil, fmt.Errorf("invalid m3u8: missing #EXTM3U header")
	}

	var currentKey *Key
	var currentStreamInfo *StreamInfo
	sequence := 0
	discontinuity := false

	for i := 1; i < len(lines); i++ {
		line := strings.TrimSpace(lines[i])
		if line == "" || strings.HasPrefix(line, "#EXT-X-DATERANGE") {
			continue
		}

		switch {
		case line == "#EXT-X-ENDLIST":
			pl.Endlist = true

		case strings.HasPrefix(line, "#EXT-X-VERSION:"):
			pl.Version, _ = strconv.Atoi(parseValue(line))

		case strings.HasPrefix(line, "#EXT-X-TARGETDURATION:"):
			pl.TargetDuration, _ = strconv.ParseFloat(parseValue(line), 64)

		case strings.HasPrefix(line, "#EXT-X-MEDIA-SEQUENCE:"):
			pl.MediaSequence, _ = strconv.Atoi(parseValue(line))
			sequence = pl.MediaSequence

		case strings.HasPrefix(line, "#EXT-X-PLAYLIST-TYPE:"):
			pl.PlaylistType = parseValue(line)

		case strings.HasPrefix(line, "#EXT-X-INDEPENDENT-SEGMENTS"):
			pl.IndependentSegments = true

		case line == "#EXT-X-DISCONTINUITY":
			discontinuity = true

		case strings.HasPrefix(line, "#EXT-X-KEY:"):
			currentKey = parseKeyTag(line)

		case strings.HasPrefix(line, "#EXTINF:"):
			seg := parseExtInf(line)
			if seg != nil {
				seg.Sequence = sequence
				seg.Key = currentKey
				seg.Discontinuity = discontinuity
				discontinuity = false

				if i+1 < len(lines) {
					seg.URI = strings.TrimSpace(lines[i+1])
					if !strings.HasPrefix(seg.URI, "#") {
						i++
					}
				}
				pl.Segments = append(pl.Segments, seg)
				sequence++
			}

		case strings.HasPrefix(line, "#EXT-X-STREAM-INF:"):
			currentStreamInfo = parseStreamInfo(line)

		case strings.HasPrefix(line, "#EXT-X-MEDIA:"):
			mi := parseMediaTag(line)
			if mi != nil {
				pl.MediaInfos = append(pl.MediaInfos, mi)
			}

		case strings.HasPrefix(line, "#EXT-X-MAP:"):
			uri, byterange := parseMapTag(line)
			if len(pl.Segments) > 0 {
				pl.Segments[len(pl.Segments)-1].InitSegment = uri
				pl.Segments[len(pl.Segments)-1].ByteRange = byterange
			}

		case strings.HasPrefix(line, "#EXT-X-BYTERANGE:"):
			if len(pl.Segments) > 0 {
				pl.Segments[len(pl.Segments)-1].ByteRange = parseValue(line)
			}

		default:
			if currentStreamInfo != nil && !strings.HasPrefix(line, "#") {
				currentStreamInfo.URI = line
				pl.StreamInfos = append(pl.StreamInfos, currentStreamInfo)
				currentStreamInfo = nil
				pl.IsMaster = true
			}
		}
	}

	if len(pl.Segments) > 0 {
		pl.IsVariant = true
	}

	return pl, nil
}

func ResolveURIs(pl *Playlist, baseURL string) error {
	base, err := url.Parse(baseURL)
	if err != nil {
		return fmt.Errorf("invalid base URL: %w", err)
	}

	for _, seg := range pl.Segments {
		if u, err := url.Parse(seg.URI); err == nil && !u.IsAbs() {
			seg.URI = resolveURL(base, seg.URI)
		}
		if seg.Key != nil && seg.Key.URI != "" {
			if u, err := url.Parse(seg.Key.URI); err == nil && !u.IsAbs() {
				seg.Key.URI = resolveURL(base, seg.Key.URI)
			}
		}
		if seg.InitSegment != "" {
			if u, err := url.Parse(seg.InitSegment); err == nil && !u.IsAbs() {
				seg.InitSegment = resolveURL(base, seg.InitSegment)
			}
		}
	}

	for _, si := range pl.StreamInfos {
		if u, err := url.Parse(si.URI); err == nil && !u.IsAbs() {
			si.URI = resolveURL(base, si.URI)
		}
	}

	for _, mi := range pl.MediaInfos {
		if mi.URI != "" {
			if u, err := url.Parse(mi.URI); err == nil && !u.IsAbs() {
				mi.URI = resolveURL(base, mi.URI)
			}
		}
	}

	return nil
}

func resolveURL(base *url.URL, rawURL string) string {
	u, err := url.Parse(rawURL)
	if err != nil {
		return rawURL
	}
	return base.ResolveReference(u).String()
}

func parseValue(line string) string {
	if idx := strings.IndexByte(line, ':'); idx != -1 {
		return strings.TrimSpace(line[idx+1:])
	}
	return ""
}

func parseExtInf(line string) *Segment {
	v := parseValue(line)
	seg := &Segment{}
	if idx := strings.IndexByte(v, ','); idx != -1 {
		seg.Duration, _ = strconv.ParseFloat(strings.TrimSpace(v[:idx]), 64)
		seg.Title = strings.TrimSpace(v[idx+1:])
	} else {
		seg.Duration, _ = strconv.ParseFloat(strings.TrimSpace(v), 64)
	}
	return seg
}

func parseKeyTag(line string) *Key {
	key := &Key{}
	attrs := parseAttributes(line)

	key.Method = attrs["METHOD"]
	key.URI = trimQuotes(attrs["URI"])
	key.IV = trimQuotes(attrs["IV"])
	key.KeyFormat = trimQuotes(attrs["KEYFORMAT"])
	key.KeyFormatVersions = trimQuotes(attrs["KEYFORMATVERSIONS"])

	return key
}

func parseStreamInfo(line string) *StreamInfo {
	si := &StreamInfo{}
	attrs := parseAttributes(line)

	si.Bandwidth, _ = strconv.Atoi(attrs["BANDWIDTH"])
	si.AverageBandwidth, _ = strconv.Atoi(attrs["AVERAGE-BANDWIDTH"])
	si.Codecs = trimQuotes(attrs["CODECS"])
	si.Resolution = trimQuotes(attrs["RESOLUTION"])
	si.Audio = trimQuotes(attrs["AUDIO"])
	si.Video = trimQuotes(attrs["VIDEO"])
	si.Subtitles = trimQuotes(attrs["SUBTITLES"])

	if fr, ok := attrs["FRAME-RATE"]; ok {
		si.FrameRate, _ = strconv.ParseFloat(fr, 64)
	}

	return si
}

func parseMediaTag(line string) *MediaInfo {
	mi := &MediaInfo{}
	attrs := parseAttributes(line)

	mi.Type = trimQuotes(attrs["TYPE"])
	mi.GroupID = trimQuotes(attrs["GROUP-ID"])
	mi.Name = trimQuotes(attrs["NAME"])
	mi.Language = trimQuotes(attrs["LANGUAGE"])
	mi.Default = attrs["DEFAULT"] == "YES"
	mi.AutoSelect = attrs["AUTO-SELECT"] == "YES"
	mi.Forced = attrs["FORCED"] == "YES"
	mi.URI = trimQuotes(attrs["URI"])

	return mi
}

func parseMapTag(line string) (uri, byterange string) {
	attrs := parseAttributes(line)
	return trimQuotes(attrs["URI"]), attrs["BYTERANGE"]
}

func parseAttributes(line string) map[string]string {
	attrs := make(map[string]string)
	idx := strings.IndexByte(line, ':')
	if idx == -1 {
		return attrs
	}
	rest := line[idx+1:]

	var key, value string
	inValue := false
	inQuotes := false
	i := 0

	for i < len(rest) {
		if !inValue {
			if rest[i] == '=' {
				inValue = true
				i++
			} else {
				key += string(rest[i])
				i++
			}
		} else {
			if rest[i] == '"' && !inQuotes {
				inQuotes = true
				i++
				continue
			}
			if rest[i] == '"' && inQuotes {
				inQuotes = false
				i++
				continue
			}
			if rest[i] == ',' && !inQuotes {
				attrs[strings.TrimSpace(key)] = strings.TrimSpace(value)
				key = ""
				value = ""
				inValue = false
				i++
				continue
			}
			value += string(rest[i])
			i++
		}
	}

	if key != "" {
		attrs[strings.TrimSpace(key)] = strings.TrimSpace(value)
	}

	return attrs
}

func trimQuotes(s string) string {
	return strings.Trim(s, "\"")
}

func (pl *Playlist) BestStream() *StreamInfo {
	if len(pl.StreamInfos) == 0 {
		return nil
	}
	best := pl.StreamInfos[0]
	for _, si := range pl.StreamInfos[1:] {
		if si.Bandwidth > best.Bandwidth {
			best = si
		}
	}
	return best
}

func (pl *Playlist) TotalDuration() float64 {
	var total float64
	for _, seg := range pl.Segments {
		total += seg.Duration
	}
	return total
}

func (pl *Playlist) AbsoluteURIs(baseURL string) error {
	if !strings.HasPrefix(baseURL, "http://") && !strings.HasPrefix(baseURL, "https://") {
		baseURL = "https://" + baseURL
	}
	base, err := url.Parse(baseURL)
	if err != nil {
		return err
	}
	baseDir := base.Path
	if idx := strings.LastIndex(baseDir, "/"); idx > 0 {
		baseDir = baseDir[:idx+1]
	} else {
		baseDir = "/"
	}
	baseDirURL := &url.URL{Scheme: base.Scheme, Host: base.Host, Path: baseDir}

	for _, seg := range pl.Segments {
		if !isAbsolute(seg.URI) {
			seg.URI = baseDirURL.ResolveReference(&url.URL{Path: path.Clean(seg.URI)}).String()
		}
		if seg.Key != nil && seg.Key.URI != "" && !isAbsolute(seg.Key.URI) {
			seg.Key.URI = baseDirURL.ResolveReference(&url.URL{Path: path.Clean(seg.Key.URI)}).String()
		}
		if seg.InitSegment != "" && !isAbsolute(seg.InitSegment) {
			seg.InitSegment = baseDirURL.ResolveReference(&url.URL{Path: path.Clean(seg.InitSegment)}).String()
		}
	}
	return nil
}

func isAbsolute(uri string) bool {
	return strings.HasPrefix(uri, "http://") || strings.HasPrefix(uri, "https://") || strings.HasPrefix(uri, "//")
}
