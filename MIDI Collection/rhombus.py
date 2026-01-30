import mido
import numpy as np
import matplotlib.pyplot as plt
import argparse
import os
import glob
from pathlib import Path
import colorsys

class MIDIDialGrid:
    def __init__(self, midi_directory, output_path=None, dpi=300, 
                 dial_size=2.0, max_files=None, cols=4):
        self.midi_directory = midi_directory
        self.output_path = output_path
        self.dpi = dpi
        self.dial_size = dial_size
        self.max_files = max_files
        self.cols = cols
        
        self.song_data = []
        
        # Load all MIDI files
        self.load_all_midi_files()
        
    def get_song_initials(self, filename):
        """Convert filename to initials (Underneath_the_Silver_Sky.mid -> UtSS)"""
        name = Path(filename).stem
        name = name.replace('_', ' ').replace('-', ' ')
        words = name.split()
        
        if len(words) == 1:
            return name[:3].upper()
        else:
            initials = ''.join(word[0] for word in words if word)
            return initials.upper() if len(initials) > 1 else name[:3].upper()
    
    def get_instrument_name(self, program_number, is_drum=False):
        """Convert MIDI program number to instrument name"""
        if is_drum:
            return "DRUMS"
            
        instrument_names = [
            "Piano", "BrightPiano", "EPiano", "HonkyTonk", "EPiano1", "EPiano2", 
            "Harpsichord", "Clavinet", "Celesta", "Glockenspiel", "MusicBox", 
            "Vibraphone", "Marimba", "Xylophone", "Bells", "Dulcimer", "Organ", 
            "PercOrgan", "RockOrgan", "ChurchOrg", "ReedOrg", "Accordion", 
            "Harmonica", "Accordion2", "GuitarNyl", "GuitarSteel", "GuitarJazz", 
            "GuitarClean", "GuitarMuted", "GuitarOD", "GuitarDist", "GuitarHarm", 
            "BassAcoustic", "BassFinger", "BassPick", "BassFretless", "BassSlap1", 
            "BassSlap2", "SynthBass1", "SynthBass2", "Violin", "Viola", "Cello", 
            "Contrabass", "StringsTrm", "StringsPizz", "Harp", "Timpani", "Strings1", 
            "Strings2", "SynthStr1", "SynthStr2", "Choir", "Voice", "SynthVoice", 
            "OrchHit", "Trumpet", "Trombone", "Tuba", "TrumpetMut", "FrenchHorn", 
            "Brass", "SynthBrass1", "SynthBrass2", "SopranoSax", "AltoSax", 
            "TenorSax", "BariSax", "Oboe", "EnglishHorn", "Bassoon", "Clarinet", 
            "Piccolo", "Flute", "Recorder", "PanFlute", "Bottle", "Shakuhachi", 
            "Whistle", "Ocarina", "Square", "Sawtooth", "Calliope", "Chiff", 
            "Charang", "VoiceLead", "Fifths", "BassLead", "NewAge", "Warm", 
            "Polysynth", "ChoirPad", "Bowed", "Metallic", "Halo", "Sweep", "Rain", 
            "Soundtrack", "Crystal", "Atmosphere", "Brightness", "Goblins", 
            "Echoes", "SciFi", "Sitar", "Banjo", "Shamisen", "Koto", "Kalimba", 
            "Bagpipe", "Fiddle", "Shanai", "Bell", "Agogo", "SteelDrums", 
            "Woodblock", "Taiko", "Tom", "SynthDrum", "RevCymbal", "FretNoise", 
            "Breath", "Seashore", "Bird", "Telephone", "Helicopter", "Applause", "Gun"
        ]
        
        if 0 <= program_number < len(instrument_names):
            return instrument_names[program_number]
        return f"Inst{program_number}"
    
    def get_instrument_color(self, instrument_num, is_drum=False):
        """Generate base color for instrument"""
        if is_drum:
            base_hue = 0.0  # Red for drums
            saturation = 0.9
            lightness = 0.6
        else:
            # Distribute hues based on instrument family
            if instrument_num < 8:  # Pianos
                base_hue = 0.1  # Orange
            elif instrument_num < 24:  # Guitars/Basses
                base_hue = 0.3  # Green
            elif instrument_num < 40:  # Strings
                base_hue = 0.6  # Blue
            elif instrument_num < 56:  # Brass
                base_hue = 0.8  # Purple
            elif instrument_num < 72:  # Woodwinds
                base_hue = 0.15  # Yellow
            elif instrument_num < 88:  # Synths
                base_hue = 0.7  # Pink
            else:  # Ethnic
                base_hue = 0.5  # Teal
            
            saturation = 0.8
            lightness = 0.65
        
        rgb = colorsys.hls_to_rgb(base_hue, lightness, saturation)
        return rgb
    
    def load_all_midi_files(self):
        """Load and parse all MIDI files in directory"""
        midi_patterns = ['*.mid']
        all_midi_files = []
        
        for pattern in midi_patterns:
            all_midi_files.extend(glob.glob(os.path.join(self.midi_directory, pattern)))
        
        if not all_midi_files:
            print(f"No MIDI files found in {self.midi_directory}")
            return False
        
        # Sort files and apply limit
        all_midi_files.sort()
        if self.max_files:
            all_midi_files = all_midi_files[:self.max_files]
        
        print(f"Found {len(all_midi_files)} MIDI files")
        
        # Parse each file
        for midi_file in all_midi_files:
            self.parse_midi_file(midi_file)
        
        return True
    
    def parse_midi_file(self, midi_path):
        """Parse a single MIDI file - GROUP BY INSTRUMENT ONLY, NOT CHANNEL"""
        try:
            midi = mido.MidiFile(midi_path)
            filename = os.path.basename(midi_path)
            initials = self.get_song_initials(filename)
            
            # Initialize program changes
            program_changes = {i: 0 for i in range(16)}
            program_changes[9] = 0  # Channel 10 is drums
            
            # Parse program changes first
            for track in midi.tracks:
                current_time = 0
                for msg in track:
                    current_time += msg.time
                    if msg.type == 'program_change':
                        program_changes[msg.channel] = msg.program
            
            # Group notes by instrument ONLY (program number), ignore channel
            instrument_notes = {}
            
            for track in midi.tracks:
                current_time = 0
                current_pan = 64
                current_pitch_bend = 8192
                current_modulation = 0
                current_expression = 127
                
                for msg in track:
                    current_time += msg.time
                    
                    if msg.type == 'control_change':
                        if msg.control == 10:  # Pan
                            current_pan = msg.value
                        elif msg.control == 1:  # Modulation
                            current_modulation = msg.value
                        elif msg.control == 11:  # Expression
                            current_expression = msg.value
                    
                    elif msg.type == 'pitchwheel':
                        current_pitch_bend = msg.pitch
                    
                    elif msg.type == 'note_on' and msg.velocity > 0:
                        # USE ONLY PROGRAM NUMBER AS KEY - IGNORE CHANNEL
                        instrument_num = program_changes[msg.channel]
                        is_drum = (msg.channel == 9)
                        instrument_key = instrument_num  # Just use program number
                        
                        if instrument_key not in instrument_notes:
                            instrument_notes[instrument_key] = {
                                'notes': [],
                                'instrument': instrument_num,
                                'is_drum': is_drum
                            }
                        
                        # Store note with timing info
                        instrument_notes[instrument_key]['notes'].append({
                            'start_time': current_time,
                            'pitch': msg.note,
                            'velocity': msg.velocity,
                            'pan': current_pan,
                            'pitch_bend': current_pitch_bend,
                            'modulation': current_modulation,
                            'expression': current_expression,
                            'duration': 0  # Will be set by note_off
                        })
                    
                    elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                        # Find matching note_on and set duration
                        for inst_key, inst_data in instrument_notes.items():
                            for note in inst_data['notes']:
                                if (note['pitch'] == msg.note and 
                                    note['duration'] == 0 and 
                                    abs(current_time - note['start_time']) < 1000):  # Reasonable match
                                    note['end_time'] = current_time
                                    note['duration'] = current_time - note['start_time']
                                    break
            
            # Filter out instruments with no valid notes
            valid_instruments = {}
            for inst_key, inst_data in instrument_notes.items():
                valid_notes = [note for note in inst_data['notes'] if 'end_time' in note]
                if valid_notes:
                    valid_instruments[inst_key] = {
                        'notes': valid_notes,
                        'instrument': inst_data['instrument'],
                        'is_drum': inst_data['is_drum'],
                        'note_count': len(valid_notes)
                    }
            
            if not valid_instruments:
                print(f"No valid instruments found in {filename}")
                return
            
            # Calculate max time
            all_times = []
            for inst_data in valid_instruments.values():
                for note in inst_data['notes']:
                    all_times.append(note['end_time'])
            max_time = max(all_times) if all_times else 1
            
            # Convert to list and sort by instrument type
            instruments_list = []
            for inst_data in valid_instruments.values():
                instruments_list.append(inst_data)
            
            # Sort: drums first, then by instrument number
            instruments_list.sort(key=lambda x: (not x['is_drum'], x['instrument']))
            
            self.song_data.append({
                'filename': filename,
                'initials': initials,
                'instruments': instruments_list,
                'max_time': max_time,
                'total_notes': sum(inst['note_count'] for inst in instruments_list)
            })
            
            print(f"Parsed {filename}: {initials} - {len(instruments_list)} instruments, {sum(inst['note_count'] for inst in instruments_list)} notes")
            
        except Exception as e:
            print(f"Error parsing {midi_path}: {e}")
    
    def create_dial_grid(self):
        """Create grid of dials - each column is a song"""
        if not self.song_data:
            print("No song data to visualize")
            return False
        
        num_songs = len(self.song_data)
        self.cols = min(self.cols, num_songs)  # Don't exceed available songs
        
        # Calculate rows needed
        max_instruments = max(len(song['instruments']) for song in self.song_data)
        rows = max_instruments
        
        print(f"Creating grid: {self.cols} columns × {rows} rows")
        
        # Create figure
        fig_width = self.cols * self.dial_size
        fig_height = rows * self.dial_size * 0.8
        
        self.fig, self.axes = plt.subplots(
            rows, self.cols,
            figsize=(fig_width, fig_height),
            subplot_kw=dict(projection='polar'),
            facecolor='black'
        )
        
        # Handle single row/column cases
        if rows == 1 and self.cols == 1:
            self.axes = np.array([[self.axes]])
        elif rows == 1:
            self.axes = self.axes.reshape(1, -1)
        elif self.cols == 1:
            self.axes = self.axes.reshape(-1, 1)
        
        # Plot each song in its column
        for col in range(self.cols):
            if col < num_songs:
                song = self.song_data[col]
                instruments = song['instruments']
                
                # Add song initials at top of column
                self.fig.text(
                    (col + 0.5) / self.cols, 0.98,
                    song['initials'],
                    color='white', ha='center', va='top',
                    fontsize=14, weight='bold',
                    transform=self.fig.transFigure
                )
                
                # Plot each instrument in this song
                for row in range(rows):
                    if row < len(instruments):
                        ax = self.axes[row, col]
                        instrument = instruments[row]
                        self.plot_instrument_dial(ax, instrument, song)
                    else:
                        # Empty cell
                        ax = self.axes[row, col]
                        ax.set_facecolor('black')
                        ax.set_axis_off()
        
        # Remove any empty subplots and adjust layout
        plt.tight_layout(pad=1.0)
        return True
    
    def plot_instrument_dial(self, ax, instrument, song):
        """Plot a single instrument dial with 0.5 width notes"""
        notes = instrument['notes']
        max_time = song['max_time']
        instrument_num = instrument['instrument']
        is_drum = instrument['is_drum']
        
        # Base color for this instrument
        base_color = self.get_instrument_color(instrument_num, is_drum)
        base_h, base_l, base_s = colorsys.rgb_to_hls(*base_color)
        
        # Pitch to radius mapping
        pitches = sorted(set(note['pitch'] for note in notes))
        if not pitches:
            return
            
        pitch_to_radius = {pitch: i for i, pitch in enumerate(pitches)}
        total_rings = len(pitches)
        ring_spacing = 1.0 / total_rings
        effective_ring_width = ring_spacing * 0.5  # Fixed 0.5 width as requested
        
        # Plot notes with parameter modulations
        for note in notes:
            start_angle = 2 * np.pi * (note['start_time'] / max_time)
            end_angle = 2 * np.pi * (note['end_time'] / max_time)
            
            ring_index = pitch_to_radius[note['pitch']]
            inner_radius = ring_index * ring_spacing
            outer_radius = inner_radius + effective_ring_width
            
            angle_width = max(end_angle - start_angle, 0.005)
            
            # Parameter-based color modulations
            h, l, s = base_h, base_l, base_s
            
            # Velocity affects lightness
            velocity_factor = note['velocity'] / 127.0
            l_mod = 0.3 + (velocity_factor * 0.4)
            
            # Pan affects hue shift
            pan_factor = (note['pan'] - 64) / 64.0
            h_mod = h + (pan_factor * 0.1)
            
            # Pitch bend affects saturation
            pitch_bend_factor = abs(note['pitch_bend'] - 8192) / 8192.0
            s_mod = s * (0.7 + pitch_bend_factor * 0.3)
            
            # Modulation adds variation
            mod_factor = note['modulation'] / 127.0
            h_mod += mod_factor * 0.05
            
            # Expression affects alpha
            expr_factor = note['expression'] / 127.0
            alpha = 0.4 + (expr_factor * 0.5)
            
            # Ensure valid ranges
            h_mod = h_mod % 1.0
            l_mod = max(0.2, min(0.8, l_mod))
            s_mod = max(0.3, min(1.0, s_mod))
            alpha = max(0.3, min(1.0, alpha))
            
            # Convert to RGB
            note_color = colorsys.hls_to_rgb(h_mod, l_mod, s_mod)
            
            # Boost drums
            if is_drum:
                alpha = min(alpha + 0.2, 1.0)
                note_color = tuple(min(1.0, c * 1.2) for c in note_color)
            
            theta = np.linspace(start_angle, start_angle + angle_width, 30)
            r_inner = np.full_like(theta, inner_radius)
            r_outer = np.full_like(theta, outer_radius)
            
            ax.fill_between(theta, r_inner, r_outer, 
                          color=note_color, alpha=alpha, 
                          linewidth=0, antialiased=True)
        
        # Clean dial appearance
        ax.set_theta_offset(np.pi/2)
        ax.set_theta_direction(-1)
        ax.set_ylim(0, 1)
        ax.set_axis_off()
        ax.grid(False)
        ax.set_facecolor('black')
        
        # Add subtle border
        border_theta = np.linspace(0, 2*np.pi, 100)
        border_radius = np.full_like(border_theta, 1.0)
        ax.plot(border_theta, border_radius, color=base_color, alpha=0.2, linewidth=0.5)
    
    def save_visualization(self):
        """Save the dial grid as a static image"""
        if self.create_dial_grid():
            if self.output_path is None:
                self.output_path = os.path.join(self.midi_directory, 'midi_dial_grid.png')
            
            plt.savefig(self.output_path, dpi=self.dpi, bbox_inches='tight', 
                       pad_inches=0.3, facecolor='black', edgecolor='none')
            print(f"Dial grid saved to: {self.output_path}")
            plt.close()
            return True
        return False
    
    def show_interactive(self):
        """Show the visualization interactively"""
        if self.create_dial_grid():
            plt.show()
            return True
        return False

def main():
    parser = argparse.ArgumentParser(description='MIDI Dial Grid Visualizer')
    parser.add_argument('midi_directory', help='Path to directory containing MIDI files')
    parser.add_argument('-o', '--output', help='Output image path')
    parser.add_argument('--dpi', type=int, default=300, help='Image resolution')
    parser.add_argument('--size', type=float, default=2.0, help='Dial size in inches')
    parser.add_argument('--cols', type=int, default=4, help='Number of columns')
    parser.add_argument('--max-files', type=int, help='Maximum number of files to process')
    parser.add_argument('--show', action='store_true', help='Show interactive plot instead of saving')
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.midi_directory):
        print(f"Error: {args.midi_directory} is not a valid directory")
        return
    
    visualizer = MIDIDialGrid(
        args.midi_directory,
        output_path=args.output,
        dpi=args.dpi,
        dial_size=args.size,
        max_files=args.max_files,
        cols=args.cols
    )
    
    if args.show:
        print("\nMIDI Dial Grid Visualizer")
        print("=========================")
        print(f"Showing {len(visualizer.song_data)} songs in {args.cols} columns")
        visualizer.show_interactive()
    else:
        if visualizer.save_visualization():
            print(f"Successfully created dial grid with {len(visualizer.song_data)} songs")
        else:
            print("Failed to create visualization")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        main()
    else:
        print("MIDI Dial Grid Visualizer")
        print("=========================")
        print("\nUsage: python midi_grid.py <midi_directory> [options]")
        print("\nExamples:")
        print("python midi_grid.py ./midi_files                    # Save 4-column grid")
        print("python midi_grid.py ./midi_files --show             # Interactive view")
        print("python midi_grid.py ./midi_files --cols 6           # 6-column grid")
        print("python midi_grid.py ./midi_files --size 1.5         # Smaller dials")
        print("python midi_grid.py ./midi_files --max-files 8      # Limit to 8 songs")