window.stemSessions = window.stemSessions || {};
window.stemSessions['session{session.paddedCounter}'] = window.stemSessions['session{session.paddedCounter}'] || {
  index: 'session{session.paddedCounter}',
  counter: '{session.counter}',
  date: '{session.date}',
  day: '{session.day}',
  month: '{session.month}',
  year: '{session.year}',
  title: 'Jam session #{session.counter}',
  tracks: {},
  images: [
{images}
  ],
  videos: [
{videos}
  ]
};
window.stemSessions['session{session.paddedCounter}'].tracks['{track.letter}'] = window.stemSessions['session{session.paddedCounter}'].tracks['{track.letter}'] || {
  title: '{track.title}',
  artist: '{track.artist}',
  trackLetter: '{track.letter}',
  trackNumber: '{track.number}',
  session: 'session{session.paddedCounter}',
  genre: '{track.genre}',
  duration: {track.duration},
  byteSize: {track.byteSize},
  bpm: {track.bpm},
  dbLevelBoundries: {track.dbLevelsInputFiles},
  stems: [
{stems}
  ]
};
