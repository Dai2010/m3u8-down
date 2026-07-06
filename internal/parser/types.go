package parser

type Segment struct {
	URI        string
	Duration   float64
	Title      string
	Sequence   int
	Discontinuity bool
	Key        *Key
	InitSegment string
	ByteRange  string
}

type Key struct {
	Method string
	URI    string
	IV     string
	KeyFormat string
	KeyFormatVersions string
}

type StreamInfo struct {
	Bandwidth      int
	AverageBandwidth int
	Codecs        string
	Resolution    string
	FrameRate     float64
	Audio         string
	Video         string
	Subtitles     string
	URI           string
}

type MediaInfo struct {
	Type         string
	GroupID      string
	Name         string
	Language     string
	Default      bool
	AutoSelect   bool
	Forced       bool
	URI          string
}

type Playlist struct {
	Version         int
	TargetDuration  float64
	MediaSequence   int
	PlaylistType    string
	Segments        []*Segment
	StreamInfos     []*StreamInfo
	MediaInfos      []*MediaInfo
	IsMaster        bool
	IsVariant       bool
	Endlist         bool
	IndependentSegments bool
}
