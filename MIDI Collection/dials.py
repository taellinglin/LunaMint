import mido
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import argparse
import os
import time
import pygame.midi
from matplotlib.widgets import Button

class CircularMIDIVisualizer:
    def __init__(self, midi_file_path, output_path=None, dpi=300, 
                 ring_width=0.8, color_palette='viridis', 
                 dial_size=3, rows=None, cols=None, playback=False, hide_labels=False):
        self.midi_file_path = midi_file_path
        self.output_path = output_path
        self.dpi = dpi
        self.ring_width = ring_width
        self.color_palette = color_palette
        self.dial_size = dial_size
        self.rows = rows
        self.cols = cols
        self.playback_mode = playback
        self.hide_labels = hide_labels
        
        self.notes = []
        self.program_changes = {}
        self.track_playheads = {}
        self.is_playing = False
        self.start_time = None
        self.current_time = 0
        self.animation = None
        self.midi_out = None
        
        if self.playback_mode:
            # Initialize pygame MIDI for playback
            pygame.midi.init()
            try:
                self.midi_out = pygame.midi.Output(pygame.midi.get_default_output_id())
                print("MIDI output initialized for playback")
            except:
                print("No MIDI output device found. Audio will not play.")
                self.midi_out = None
        
        # Load MIDI file
        self.load_midi_file()
        
    def load_midi_file(self):
        """Load and parse MIDI file with instrument data"""
        try:
            self.midi = mido.MidiFile(self.midi_file_path)
            print(f"Loaded MIDI file: {len(self.midi.tracks)} tracks, {self.midi.length:.2f} seconds")
            print(f"Tempo: {self.midi.ticks_per_beat} ticks per beat")
        except Exception as e:
            print(f"Error loading MIDI file: {e}")
            return False
            
        # Initialize program changes
        self.program_changes = {i: 0 for i in range(16)}
        self.program_changes[9] = 25  # Channel 10 is drums
        
        # Parse program changes first
        for track in self.midi.tracks:
            current_time = 0
            for msg in track:
                current_time += msg.time
                if msg.type == 'program_change':
                    self.program_changes[msg.channel] = msg.program
        
        # Parse notes for visualization
        self.parse_notes_for_visualization()
        
        # Parse all MIDI events for playback
        self.parse_midi_events_for_playback()
        
        return True
    
    def parse_notes_for_visualization(self):
        """Parse notes specifically for the circular visualization"""
        current_time = 0
        active_notes = {}
        
        # Group notes by track
        self.track_notes = {}
        
        for i, track in enumerate(self.midi.tracks):
            current_time = 0
            track_notes_list = []
            active_notes = {}
            
            for msg in track:
                current_time += msg.time
                if msg.type == 'note_on' and msg.velocity > 0:
                    active_notes[(msg.channel, msg.note)] = {
                        'start_time': current_time,
                        'velocity': msg.velocity,
                        'track': i,
                        'channel': msg.channel,
                        'instrument': self.program_changes[msg.channel]
                    }
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    key = (msg.channel, msg.note)
                    if key in active_notes:
                        note_info = active_notes[key]
                        note_data = {
                            'pitch': msg.note,
                            'start_time': note_info['start_time'],
                            'end_time': current_time,
                            'duration': current_time - note_info['start_time'],
                            'velocity': note_info['velocity'],
                            'track': note_info['track'],
                            'channel': note_info['channel'],
                            'instrument': note_info['instrument'],
                            'is_drum': note_info['channel'] == 9
                        }
                        track_notes_list.append(note_data)
                        self.notes.append(note_data)
                        del active_notes[key]
            
            # Only add track if it has notes
            if track_notes_list:
                self.track_notes[i] = track_notes_list
        
        if not self.track_notes:
            print("No tracks with notes found in MIDI file")
            return False
            
        # Calculate max time across all tracks
        all_times = []
        for track_notes in self.track_notes.values():
            for note in track_notes:
                all_times.append(note['end_time'])
        self.max_time = max(all_times) if all_times else 1
        
        print(f"Parsed {len(self.notes)} notes across {len(self.track_notes)} tracks")
        return True
    
    def parse_midi_events_for_playback(self):
        """Parse all MIDI events for proper playback timing"""
        self.all_midi_events = []
        current_time = 0
        
        # Use mido's built-in timing for accurate playback
        for msg in self.midi:
            current_time += msg.time
            if msg.type in ['note_on', 'note_off', 'program_change']:
                self.all_midi_events.append({
                    'msg': msg,
                    'time': current_time,
                    'type': msg.type
                })
        
        if self.all_midi_events:
            self.max_time = max(event['time'] for event in self.all_midi_events)
            print(f"Parsed {len(self.all_midi_events)} MIDI events for playback")
        
        self.played_events = set()
    
    def get_instrument_name(self, program_number):
        """Convert MIDI program number to instrument name"""
        instrument_names = [
            "Piano", "Bright Piano", "Electric Piano", "Honky-tonk",
            "EPiano1", "EPiano2", "Harpsichord", "Clavinet",
            "Celesta", "Glockenspiel", "Music Box", "Vibraphone", "Marimba", "Xylophone", "Bells", "Dulcimer",
            "Organ", "Perc Organ", "Rock Organ", "Church Organ", "Reed Organ", "Accordion", "Harmonica", "Accordion2",
            "GuitarNylon", "GuitarSteel", "GuitarJazz", "GuitarClean",
            "GuitarMuted", "GuitarOverdrive", "GuitarDistort", "GuitarHarmonics",
            "BassAcoustic", "BassFinger", "BassPick", "BassFretless",
            "BassSlap1", "BassSlap2", "SynthBass1", "SynthBass2",
            "Violin", "Viola", "Cello", "Contrabass", "StringsTremolo", "StringsPizz", "Harp", "Timpani",
            "Strings1", "Strings2", "SynthStrings1", "SynthStrings2", "Choir", "Voice", "SynthVoice", "OrchestraHit",
            "Trumpet", "Trombone", "Tuba", "TrumpetMuted", "FrenchHorn", "Brass", "SynthBrass1", "SynthBrass2",
            "SopranoSax", "AltoSax", "TenorSax", "BaritoneSax", "Oboe", "EnglishHorn", "Bassoon", "Clarinet",
            "Piccolo", "Flute", "Recorder", "PanFlute", "Bottle", "Shakuhachi", "Whistle", "Ocarina",
            "Square", "Sawtooth", "Calliope", "Chiff", "Charang", "VoiceLead", "Fifths", "BassLead",
            "NewAge", "Warm", "Polysynth", "ChoirPad", "Bowed", "Metallic", "Halo", "Sweep",
            "Rain", "Soundtrack", "Crystal", "Atmosphere", "Brightness", "Goblins", "Echoes", "Sci-fi",
            "Sitar", "Banjo", "Shamisen", "Koto", "Kalimba", "Bagpipe", "Fiddle", "Shanai",
            "Bell", "Agogo", "SteelDrums", "Woodblock", "Taiko", "Tom", "SynthDrum", "ReverseCymbal",
            "FretNoise", "Breath", "Seashore", "Bird", "Telephone", "Helicopter", "Applause", "Gunshot"
        ]
        
        if 0 <= program_number < len(instrument_names):
            return instrument_names[program_number]
        return f"Inst{program_number}"
    
    def create_track_dials(self):
        """Create individual circular dials for each track"""
        num_tracks = len(self.track_notes)
        
        # Calculate grid layout
        if self.rows is None and self.cols is None:
            # Auto-calculate grid
            self.cols = int(np.ceil(np.sqrt(num_tracks)))
            self.rows = int(np.ceil(num_tracks / self.cols))
        elif self.rows is None:
            self.rows = int(np.ceil(num_tracks / self.cols))
        elif self.cols is None:
            self.cols = int(np.ceil(num_tracks / self.rows))
        
        # Create figure
        fig_width = self.cols * self.dial_size
        fig_height = self.rows * self.dial_size
        
        if self.playback_mode:
            # Add extra space for playback controls
            fig_height += 1
        
        self.fig, self.axes = plt.subplots(self.rows, self.cols, 
                                          figsize=(fig_width, fig_height),
                                          subplot_kw=dict(projection='polar'),
                                          facecolor='black')
        
        # Handle single subplot case
        if num_tracks == 1:
            self.axes = np.array([[self.axes]])
        elif self.rows == 1:
            self.axes = self.axes.reshape(1, -1)
        elif self.cols == 1:
            self.axes = self.axes.reshape(-1, 1)
        
        # Flatten axes for easier iteration
        flat_axes = self.axes.flatten()
        
        # Get color palette for tracks
        cmap = plt.colormaps[self.color_palette]
        self.track_colors = {}
        for i, track_num in enumerate(self.track_notes.keys()):
            self.track_colors[track_num] = cmap(i / max(1, len(self.track_notes) - 1))
        
        # Initialize playheads - ALL DIALS USE SAME TIMING
        self.track_playheads = {}
        
        # Plot each track
        for idx, (track_num, track_notes) in enumerate(self.track_notes.items()):
            if idx >= len(flat_axes):
                break
                
            ax = flat_axes[idx]
            track_color = self.track_colors[track_num]
            self.plot_track_dial(ax, track_num, track_notes, track_color)
            
            # Add playhead for playback mode - ALL DIALS SPIN TOGETHER
            if self.playback_mode:
                playhead, = ax.plot([0, 0], [0, 1], 'white', linewidth=2, alpha=0.8)
                self.track_playheads[track_num] = playhead
        
        # Hide unused subplots
        for idx in range(len(self.track_notes), len(flat_axes)):
            flat_axes[idx].set_visible(False)
        
        if self.playback_mode:
            self.setup_playback_controls()
            self.setup_instruments()
        
        # Adjust layout
        plt.tight_layout(pad=2.0, h_pad=2.0, w_pad=2.0)
        
        if not self.playback_mode:
            # Save as PNG
            if self.output_path is None:
                self.output_path = os.path.splitext(self.midi_file_path)[0] + '_track_dials.png'
            
            plt.savefig(self.output_path, dpi=self.dpi, bbox_inches='tight', 
                       facecolor='black', edgecolor='none')
            print(f"Track dials saved to: {self.output_path}")
            plt.close()
        else:
            # Start interactive playback
            self.start_playback_animation()
    def parse_notes_for_visualization(self):
        """Parse notes specifically for the circular visualization with pan and pitch data"""
        current_time = 0
        active_notes = {}
        
        # Store controller events for pan and pitch
        self.controller_events = {}
        
        # Group notes by track
        self.track_notes = {}
        
        for i, track in enumerate(self.midi.tracks):
            current_time = 0
            track_notes_list = []
            active_notes = {}
            current_pan = 64  # Default center pan
            current_pitch_bend = 8192  # Default no pitch bend (center)
            
            for msg in track:
                current_time += msg.time
                
                # Track pan changes (CC 10)
                if msg.type == 'control_change' and msg.control == 10:
                    current_pan = msg.value
                
                # Track pitch bend
                elif msg.type == 'pitchwheel':
                    current_pitch_bend = msg.pitch
                
                elif msg.type == 'note_on' and msg.velocity > 0:
                    active_notes[(msg.channel, msg.note)] = {
                        'start_time': current_time,
                        'velocity': msg.velocity,
                        'track': i,
                        'channel': msg.channel,
                        'instrument': self.program_changes[msg.channel],
                        'pan': current_pan,  # Store pan at note start
                        'pitch_bend': current_pitch_bend  # Store pitch bend at note start
                    }
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    key = (msg.channel, msg.note)
                    if key in active_notes:
                        note_info = active_notes[key]
                        note_data = {
                            'pitch': msg.note,
                            'start_time': note_info['start_time'],
                            'end_time': current_time,
                            'duration': current_time - note_info['start_time'],
                            'velocity': note_info['velocity'],
                            'track': note_info['track'],
                            'channel': note_info['channel'],
                            'instrument': note_info['instrument'],
                            'is_drum': note_info['channel'] == 9,
                            'pan': note_info['pan'],
                            'pitch_bend': note_info['pitch_bend']
                        }
                        track_notes_list.append(note_data)
                        self.notes.append(note_data)
                        del active_notes[key]
            
            # Only add track if it has notes
            if track_notes_list:
                self.track_notes[i] = track_notes_list
        
        if not self.track_notes:
            print("No tracks with notes found in MIDI file")
            return False
            
        # Calculate max time across all tracks
        all_times = []
        for track_notes in self.track_notes.values():
            for note in track_notes:
                all_times.append(note['end_time'])
        self.max_time = max(all_times) if all_times else 1
        
        print(f"Parsed {len(self.notes)} notes across {len(self.track_notes)} tracks")
        return True
    def plot_track_dial(self, ax, track_num, track_notes, track_color):
        """Plot a single track as a circular dial with RGB coloring (Velocity=Red, Pan=Green, Pitch=Blue)"""
        # Use global max time for consistent timing across all dials
        track_max_time = self.max_time
        
        # Pitch to radius mapping for this track
        pitches = sorted(set(note['pitch'] for note in track_notes))
        if not pitches:
            return
            
        pitch_to_radius = {pitch: i for i, pitch in enumerate(pitches)}
        total_rings = len(pitches)
        ring_spacing = 1.0 / total_rings
        effective_ring_width = ring_spacing * self.ring_width
        
        # Plot notes for this track with RGB coloring
        for note in track_notes:
            start_angle = 2 * np.pi * (note['start_time'] / track_max_time)
            end_angle = 2 * np.pi * (note['end_time'] / track_max_time)
            
            ring_index = pitch_to_radius[note['pitch']]
            inner_radius = ring_index * ring_spacing
            outer_radius = inner_radius + effective_ring_width
            
            angle_width = max(end_angle - start_angle, 0.005)
            
            # RGB COLOR MAPPING:
            # Red = Velocity (0-127 → 0-1)
            red = note['velocity'] / 127.0
            
            # Green = Pan (0=left, 64=center, 127=right → 0-1)
            green = note['pan'] / 127.0
            
            # Blue = Note Pitch (normalized across all pitches in this track)
            # Convert MIDI note number to 0-1 range based on track's pitch range
            min_pitch = min(pitches)
            max_pitch = max(pitches)
            if max_pitch > min_pitch:
                blue = (note['pitch'] - min_pitch) / (max_pitch - min_pitch)
            else:
                blue = 0.5  # Default if only one pitch
            
            # Alternative Blue = Fine Pitch (using pitch bend)
            # pitch_bend_normalized = (note['pitch_bend'] - 8192) / 8192.0  # -1 to +1
            # blue = (pitch_bend_normalized + 1) / 2.0  # Convert to 0-1
            
            note_color = (red, green, blue)
            
            # Alpha based on velocity for visibility
            alpha = 0.3 + (red * 0.7)  # 0.3 to 1.0 alpha
            
            # Boost drums visibility if needed
            if note['is_drum']:
                alpha = min(alpha + 0.2, 1.0)
            
            theta = np.linspace(start_angle, start_angle + angle_width, 50)
            r_inner = np.full_like(theta, inner_radius)
            r_outer = np.full_like(theta, outer_radius)
            
            ax.fill_between(theta, r_inner, r_outer, 
                        color=note_color, alpha=alpha, 
                        linewidth=0, antialiased=True)
        
        # Customize the dial
        ax.set_theta_offset(np.pi/2)
        ax.set_theta_direction(-1)
        ax.set_ylim(0, 1)
        ax.set_axis_off()
        ax.grid(False)
        
        # Add track title only if not hidden
        if not self.hide_labels:
            channel = track_notes[0]['channel'] if track_notes else 0
            instrument = self.program_changes.get(channel, 0)
            
            if channel == 9:
                title = f"Track {track_num+1}\nDRUMS"
            else:
                inst_name = self.get_instrument_name(instrument)
                title = f"Track {track_num+1}\n{inst_name}"
            
            ax.set_title(title, color='white', fontsize=8, pad=4, y=0.9, weight='bold')
    
    def setup_playback_controls(self):
        """Setup playback control buttons"""
        # Create button area
        button_height = 0.08
        button_width = 0.15
        button_margin = 0.02
        
        # Play/Pause button
        play_ax = plt.axes([0.4, 0.02, button_width, button_height])
        self.play_button = Button(play_ax, 'PLAY', color='lightgreen', hovercolor='green')
        self.play_button.on_clicked(self.toggle_playback)
        
        # Restart button
        restart_ax = plt.axes([0.55, 0.02, button_width, button_height])
        self.restart_button = Button(restart_ax, 'RESTART', color='lightblue', hovercolor='blue')
        self.restart_button.on_clicked(self.restart_playback)
        
        # Time display
        self.time_text = self.fig.text(0.75, 0.05, '00:00 / 00:00', 
                                      color='white', fontsize=12, weight='bold')
        
        # Status display
        self.status_text = self.fig.text(0.25, 0.05, 'PAUSED', 
                                       color='red', fontsize=12, weight='bold')
    
    def setup_instruments(self):
        """Set up MIDI instruments for playback"""
        if self.midi_out is None:
            return
            
        try:
            # Reset all channels
            for channel in range(16):
                self.midi_out.write_short(0xB0 + channel, 0x7B, 0)  # All notes off
        except:
            pass
        
        # Set programs for each channel that has notes
        used_channels = set()
        for track_notes in self.track_notes.values():
            for note in track_notes:
                used_channels.add(note['channel'])
        
        for channel in used_channels:
            program = self.program_changes[channel]
            if channel == 9:
                print(f"Channel 10 set to DRUMS")
            else:
                try:
                    self.midi_out.set_instrument(program, channel)
                    print(f"Channel {channel + 1} set to instrument {program}")
                except:
                    print(f"Failed to set instrument for channel {channel + 1}")
    
    def toggle_playback(self, event=None):
        """Toggle playback on/off"""
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.start_time = time.time() - self.current_time
            self.status_text.set_text('PLAYING')
            self.status_text.set_color('green')
            self.play_button.label.set_text('PAUSE')
            print("Playback started")
        else:
            self.status_text.set_text('PAUSED')
            self.status_text.set_color('red')
            self.play_button.label.set_text('PLAY')
            print("Playback paused")
            
            # Turn off all notes when pausing
            if self.midi_out:
                try:
                    for channel in range(16):
                        self.midi_out.write_short(0xB0 + channel, 0x7B, 0)
                except:
                    pass
    
    def restart_playback(self, event=None):
        """Restart playback from beginning"""
        self.current_time = 0
        self.played_events.clear()
        
        if self.midi_out:
            try:
                for channel in range(16):
                    self.midi_out.write_short(0xB0 + channel, 0x7B, 0)
            except:
                pass
        
        self.setup_instruments()
        if self.is_playing:
            self.start_time = time.time()
        print("Playback restarted")
    
    def update_playback(self, frame):
        """Update animation for playback - ALL DIALS SPIN TOGETHER"""
        if self.is_playing and self.start_time is not None:
            # Calculate current time in seconds (not MIDI ticks)
            self.current_time = time.time() - self.start_time
            
            # Calculate progress (0 to 1) - convert MIDI ticks to seconds using tempo
            # Assuming 120 BPM = 500,000 microseconds per beat
            # MIDI ticks to seconds: time_in_seconds = (ticks * tempo) / (ticks_per_beat * 1,000,000)
            tempo = 500000  # 120 BPM in microseconds per beat
            max_time_seconds = (self.max_time * tempo) / (self.midi.ticks_per_beat * 1000000.0)
            
            progress = min(self.current_time / max_time_seconds, 1.0)
            current_angle = 2 * np.pi * progress
            
            # Update ALL playheads to the same position
            for playhead in self.track_playheads.values():
                playhead.set_data([current_angle, current_angle], [0, 1])
            
            # Process MIDI events for the entire file with proper timing
            self.process_midi_events()
            
            # Update time display
            current_sec = self.current_time
            total_sec = max_time_seconds
            time_str = f'{current_sec:05.1f}s / {total_sec:05.1f}s'
            self.time_text.set_text(time_str)
            
            # Stop if finished
            if progress >= 1.0:
                self.toggle_playback()
        
        # Return empty list since we disabled blitting
        return []
    
    def process_midi_events(self):
        """Process MIDI events for the entire file with proper timing"""
        tempo = 500000  # 120 BPM in microseconds per beat
        
        for i, event in enumerate(self.all_midi_events):
            # Convert MIDI tick time to seconds
            event_time_seconds = (event['time'] * tempo) / (self.midi.ticks_per_beat * 1000000.0)
            
            if (event_time_seconds <= self.current_time and 
                i not in self.played_events and 
                self.is_playing):
                
                msg = event['msg']
                try:
                    if self.midi_out:
                        if msg.type == 'note_on' and msg.velocity > 0:
                            self.midi_out.note_on(msg.note, msg.velocity, msg.channel)
                        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                            self.midi_out.note_off(msg.note, 0, msg.channel)
                        elif msg.type == 'program_change':
                            self.midi_out.set_instrument(msg.program, msg.channel)
                except Exception as e:
                    print(f"MIDI output error: {e}")
                
                self.played_events.add(i)
    
    def start_playback_animation(self):
        """Start the playback animation"""
        # Disable blitting to fix the animation issues
        self.animation = FuncAnimation(
            self.fig, self.update_playback, 
            interval=16, blit=False, cache_frame_data=False  # blit=False fixes the issues
        )
        
        # Connect keyboard events
        self.fig.canvas.mpl_connect('key_press_event', self.on_key_press)
        self.fig.canvas.mpl_connect('close_event', self.on_close)
        
        print("\nPlayback Controls:")
        print("Click PLAY button or press SPACE to start/stop")
        print("Click RESTART button or press R to restart")
        print("ESC to exit")
        
        # Calculate actual duration for user info
        tempo = 500000  # 120 BPM
        max_time_seconds = (self.max_time * tempo) / (self.midi.ticks_per_beat * 1000000.0)
        print(f"Playback duration: {max_time_seconds:.1f} seconds")
        
        plt.show()
    
    def on_key_press(self, event):
        """Handle keyboard events"""
        if hasattr(event, 'key'):
            if event.key == ' ':
                self.toggle_playback()
            elif event.key == 'r':
                self.restart_playback()
            elif event.key == 'escape':
                self.close_player()
    
    def close_player(self):
        """Close the player and cleanup"""
        self.is_playing = False
        if self.midi_out:
            try:
                for channel in range(16):
                    self.midi_out.write_short(0xB0 + channel, 0x7B, 0)
                self.midi_out.close()
            except:
                pass
        if self.animation:
            self.animation.event_source.stop()
        plt.close()
    
    def on_close(self, event):
        """Handle window close"""
        self.close_player()
        if self.playback_mode:
            pygame.midi.quit()

def main():
    parser = argparse.ArgumentParser(description='Create circular dials for MIDI tracks with optional playback')
    parser.add_argument('midi_file', help='Path to MIDI file')
    parser.add_argument('-o', '--output', help='Output image path (for static mode)')
    parser.add_argument('--dpi', type=int, default=300, help='Image resolution')
    parser.add_argument('--width', type=float, default=0.8, help='Ring width factor')
    parser.add_argument('--palette', default='viridis', help='Color palette name')
    parser.add_argument('--size', type=float, default=3, help='Dial size in inches')
    parser.add_argument('--rows', type=int, help='Number of rows in grid')
    parser.add_argument('--cols', type=int, help='Number of columns in grid')
    parser.add_argument('--playback', action='store_true', help='Enable interactive playback mode')
    parser.add_argument('--hide', action='store_true', help='Hide track labels')
    
    args = parser.parse_args()
    
    visualizer = CircularMIDIVisualizer(
        midi_file_path=args.midi_file,
        output_path=args.output,
        dpi=args.dpi,
        ring_width=args.width,
        color_palette=args.palette,
        dial_size=args.size,
        rows=args.rows,
        cols=args.cols,
        playback=args.playback,
        hide_labels=args.hide
    )
    
    if visualizer.track_notes:
        if args.playback:
            print(f"Creating {len(visualizer.track_notes)} interactive track dials...")
        else:
            print(f"Creating {len(visualizer.track_notes)} track dials...")
        visualizer.create_track_dials()
        print("Done!")
    else:
        print("No tracks to visualize")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        main()
    else:
        print("MIDI Track Circular Dials with Playback")
        print("=======================================")
        print("\nUsage: python midi_dials.py <midi_file> [options]")
        print("\nExamples:")
        print("python midi_dials.py song.mid                          # Save as PNG")
        print("python midi_dials.py song.mid --playback               # Interactive playback")
        print("python midi_dials.py song.mid --playback --hide        # No labels with playback")
        print("python midi_dials.py song.mid --hide                   # Static image without labels")