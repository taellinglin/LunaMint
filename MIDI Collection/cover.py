import mido
import numpy as np
import matplotlib.pyplot as plt
import argparse
import os
import glob
from matplotlib.patches import Circle
import math

class MIDICoverGenerator:
    def __init__(self, input_path, output_path, dpi=1200):
        self.input_path = input_path
        self.output_path = output_path
        self.dpi = dpi
        
        # Vinyl sleeve dimensions at 1200 DPI (12.375 x 12.375 inches)
        self.fig_size = 12.375
        self.grid_size = 3  # 3x3 grid
        
        self.midi_files = []
        self.visualizations = []
        
    def find_midi_files(self):
        """Find all MIDI files in the input directory"""
        if os.path.isfile(self.input_path):
            self.midi_files = [self.input_path]
        else:
            patterns = ['*.mid']
            for pattern in patterns:
                self.midi_files.extend(glob.glob(os.path.join(self.input_path, pattern)))
        
        print(f"Found {len(self.midi_files)} MIDI files")
        return len(self.midi_files) > 0
    
    def load_midi_file(self, midi_file_path):
        """Load and parse a single MIDI file"""
        try:
            midi = mido.MidiFile(midi_file_path)
            print(f"Loaded: {os.path.basename(midi_file_path)} - {len(midi.tracks)} tracks, {midi.length:.2f}s")
            return midi
        except Exception as e:
            print(f"Error loading {midi_file_path}: {e}")
            return None
    
    def parse_midi_notes(self, midi):
        """Parse MIDI file to extract notes grouped by instrument"""
        # Get program changes
        program_changes = {i: 0 for i in range(16)}
        program_changes[9] = 25  # Channel 10 is drums
        
        # First pass: get program changes
        for track in midi.tracks:
            current_time = 0
            for msg in track:
                current_time += msg.time
                if msg.type == 'program_change':
                    program_changes[msg.channel] = msg.program
        
        # Second pass: extract notes
        instrument_notes = {}
        current_time = 0
        active_notes = {}
        
        for track in midi.tracks:
            current_time = 0
            for msg in track:
                current_time += msg.time
                
                if msg.type == 'note_on' and msg.velocity > 0:
                    instrument = program_changes[msg.channel]
                    if instrument not in active_notes:
                        active_notes[instrument] = {}
                    
                    active_notes[instrument][(msg.channel, msg.note)] = {
                        'start_time': current_time,
                        'velocity': msg.velocity,
                        'channel': msg.channel,
                        'pitch': msg.note
                    }
                
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    for instrument in active_notes:
                        key = (msg.channel, msg.note)
                        if key in active_notes[instrument]:
                            note_info = active_notes[instrument][key]
                            note_data = {
                                'pitch': msg.note,
                                'start_time': note_info['start_time'],
                                'end_time': current_time,
                                'duration': current_time - note_info['start_time'],
                                'velocity': note_info['velocity'],
                                'channel': note_info['channel'],
                                'instrument': instrument,
                                'is_drum': note_info['channel'] == 9
                            }
                            
                            if instrument not in instrument_notes:
                                instrument_notes[instrument] = []
                            instrument_notes[instrument].append(note_data)
                            del active_notes[instrument][key]
        
        # Calculate max time
        max_time = 0
        for instrument_notes_list in instrument_notes.values():
            for note in instrument_notes_list:
                max_time = max(max_time, note['end_time'])
        
        return instrument_notes, max_time if max_time > 0 else 1
    
    def get_instrument_color(self, instrument_num, total_instruments):
        """Generate a unique color for each instrument"""
        # Use HSV color space for better color distribution
        hue = (instrument_num * 0.618033988749895) % 1.0  # Golden ratio for distribution
        saturation = 0.7 + (instrument_num % 3) * 0.1  # Vary saturation
        value = 0.8 + (instrument_num % 2) * 0.15  # Vary brightness
        
        # Convert HSV to RGB
        h_i = int(hue * 6)
        f = hue * 6 - h_i
        p = value * (1 - saturation)
        q = value * (1 - f * saturation)
        t = value * (1 - (1 - f) * saturation)
        
        if h_i == 0:
            r, g, b = value, t, p
        elif h_i == 1:
            r, g, b = q, value, p
        elif h_i == 2:
            r, g, b = p, value, t
        elif h_i == 3:
            r, g, b = p, q, value
        elif h_i == 4:
            r, g, b = t, p, value
        else:
            r, g, b = value, p, q
            
        # Adjust opacity based on instrument type
        alpha = 0.3
        if instrument_num == 25:  # Drums
            alpha = 0.5
        elif instrument_num < 8:  # Pianos
            alpha = 0.4
        elif instrument_num < 16:  # Chromatic percussion
            alpha = 0.35
        elif instrument_num < 24:  # Organs
            alpha = 0.45
        elif instrument_num < 32:  # Guitars
            alpha = 0.5
        elif instrument_num < 40:  # Basses
            alpha = 0.6
            
        return (r, g, b, alpha)
    
    def draw_circular_text(self, ax, text, radius, theta_start, theta_end, fontsize=8):
        """Draw text along a circular path that follows the outer rim"""
        # Clean and prepare text
        text = text.strip()
        if not text:
            return
        
        # Calculate available circumference
        circumference = 2 * np.pi * radius * ((theta_end - theta_start) / (2 * np.pi))
        
        # Estimate character width (empirical value)
        char_width = fontsize * 0.0015 * radius
        max_chars = int(circumference / char_width)
        
        if max_chars < 4:  # Need space for text + "..."
            return
        
        # Prepare text with repetition and truncation
        if len(text) > max_chars - 3:
            # Truncate and add ellipsis
            display_text = text[:max_chars - 3] + "..."
            repeat_count = 1
        else:
            # Repeat text to fill space, leaving room for ellipsis
            available_chars = max_chars - 3  # Reserve 3 chars for ellipsis if needed
            repeat_count = max(1, available_chars // len(text))
            display_text = (text + ' ') * repeat_count
            display_text = display_text[:available_chars] + "..."
        
        # Remove any trailing space before ellipsis
        display_text = display_text.rstrip(' ') + "..."
        
        # Ensure we don't exceed available space
        display_text = display_text[:max_chars]
        
        # Calculate character positions
        theta_range = theta_end - theta_start
        char_spacing = theta_range / len(display_text)
        
        # Draw each character
        for i, char in enumerate(display_text):
            if char.strip():  # Only draw non-space characters
                theta = theta_start + (i + 0.5) * char_spacing
                
                # Position character on the circumference
                x = radius * np.cos(theta)
                y = radius * np.sin(theta)
                
                # Calculate rotation angle (tangent to the circle)
                rotation_angle = np.degrees(theta) + 90
                
                ax.text(x, y, char, 
                    rotation=rotation_angle,
                    rotation_mode='anchor',
                    ha='center', va='center',
                    fontsize=fontsize, color='white',
                    fontweight='bold',
                    transform=ax.transData)
    
    def create_dial_visualization(self, ax, midi_file_path):
        """Create a single circular dial visualization for a MIDI file"""
        midi = self.load_midi_file(midi_file_path)
        if midi is None:
            return False
        
        instrument_notes, max_time = self.parse_midi_notes(midi)
        
        if not instrument_notes:
            print(f"No notes found in {os.path.basename(midi_file_path)}")
            return False
        
        # Set up polar plot
        ax.set_theta_offset(np.pi/2)
        ax.set_theta_direction(-1)
        ax.set_ylim(0, 1)
        ax.set_axis_off()
        ax.grid(False)
        
        # Get filename for text
        filename = os.path.splitext(os.path.basename(midi_file_path))[0]
        
        # Plot each instrument's notes
        instruments = sorted(instrument_notes.keys())
        total_instruments = len(instruments)
        
        for instrument_num in instruments:
            notes = instrument_notes[instrument_num]
            if not notes:
                continue
                
            # Get unique pitches for this instrument
            pitches = sorted(set(note['pitch'] for note in notes))
            pitch_to_radius = {pitch: i for i, pitch in enumerate(pitches)}
            total_rings = len(pitches)
            
            if total_rings == 0:
                continue
                
            ring_spacing = 0.8 / total_rings  # Use 80% of radius for notes
            ring_width = ring_spacing * 0.7  # 70% of ring spacing for note width
            
            # Get instrument color
            color = self.get_instrument_color(instrument_num, total_instruments)
            
            # Plot notes
            for note in notes:
                start_angle = 2 * np.pi * (note['start_time'] / max_time)
                end_angle = 2 * np.pi * (note['end_time'] / max_time)
                
                ring_index = pitch_to_radius[note['pitch']]
                inner_radius = 0.1 + (ring_index * ring_spacing)  # Start from 10% radius
                outer_radius = inner_radius + ring_width
                
                # Ensure minimum angle width for visibility
                angle_width = max(end_angle - start_angle, 0.01)
                
                theta = np.linspace(start_angle, start_angle + angle_width, 30)
                r_inner = np.full_like(theta, inner_radius)
                r_outer = np.full_like(theta, outer_radius)
                
                # Adjust alpha based on velocity
                velocity_alpha = 0.3 + (note['velocity'] / 127.0) * 0.7
                final_alpha = color[3] * velocity_alpha
                
                ax.fill_between(theta, r_inner, r_outer, 
                            color=color[:3], alpha=final_alpha,
                            linewidth=0, antialiased=True)
        
        # Add circular text around the outer rim
        #outer_radius = 0.95  # 95% of max radius
        #self.draw_circular_text(ax, filename, outer_radius, 0, 2*np.pi, fontsize=12)
        
        return True
    
    def generate_cover(self):
        """Generate the vinyl sleeve cover with 3x3 grid of MIDI visualizations"""
        if not self.find_midi_files():
            print("No MIDI files found!")
            return False
        
        # Create figure with vinyl sleeve dimensions
        fig = plt.figure(figsize=(self.fig_size, self.fig_size), 
                        facecolor='black', dpi=self.dpi)
        
        # Create 3x3 grid of polar subplots
        axes = []
        for i in range(self.grid_size * self.grid_size):
            ax = fig.add_subplot(self.grid_size, self.grid_size, i + 1, projection='polar')
            axes.append(ax)
        
        # Generate visualizations for each MIDI file
        successful_plots = 0
        for i, midi_file in enumerate(self.midi_files):
            if i >= self.grid_size * self.grid_size:
                break
                
            if self.create_dial_visualization(axes[i], midi_file):
                successful_plots += 1
        
        # Hide unused subplots
        for i in range(successful_plots, self.grid_size * self.grid_size):
            axes[i].set_visible(False)
        
        # Adjust layout
        plt.tight_layout(pad=0.5, h_pad=0.5, w_pad=0.5)
        
        # Save as high-resolution PNG
        if self.output_path is None:
            self.output_path = 'midi_cover.png'
        
        plt.savefig(self.output_path, dpi=self.dpi, bbox_inches='tight', 
                   facecolor='black', edgecolor='none', pad_inches=0.1)
        
        print(f"Cover saved to: {self.output_path}")
        print(f"Dimensions: {self.fig_size} x {self.fig_size} inches at {self.dpi} DPI")
        print(f"Successful visualizations: {successful_plots}/{min(len(self.midi_files), 9)}")
        
        plt.close()
        return True

def main():
    parser = argparse.ArgumentParser(description='Generate vinyl sleeve cover with circular MIDI visualizations')
    parser.add_argument('input_path', help='Path to MIDI file or directory containing MIDI files')
    parser.add_argument('-o', '--output', default='front_cover.png', help='Output image path')
    
    args = parser.parse_args()
    
    generator = MIDICoverGenerator(args.input_path, args.output)
    
    if generator.generate_cover():
        print("Cover generation completed successfully!")
    else:
        print("Cover generation failed!")

if __name__ == "__main__":
    main()