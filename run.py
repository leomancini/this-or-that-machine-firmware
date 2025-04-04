import pygame
import sys
import os
import RPi.GPIO as GPIO
import time
import threading
import queue
import requests
import json
from urllib.parse import urljoin
import re
import random
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get API key from environment variables
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    print("Warning: API_KEY not found in .env file.")

# Clean up any previous configurations
try:
    GPIO.cleanup()
except:
    pass

# Use BCM numbering
GPIO.setmode(GPIO.BCM)

# Use GPIO 10 and GPIO 4
button1_pin = 10
button2_pin = 4  # Physical pin 7

# Setup pins
GPIO.setup(button1_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(button2_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Global variables
current_pair_index = 0
image_pairs = []  # Store pairs of image paths
current_images = [None, None]  # Store both images of the current pair
screen = None
running = True
button1_previous = 0
button2_previous = 0
screen_width = 0
screen_height = 0
last_button_press_time = 0
debounce_time = 0.1

# Create a command queue for thread-safe communication
command_queue = queue.Queue()

def download_missing_images():
    """Download missing images from the API"""
    try:
        # Get the list of IDs from the API
        response = requests.get(f'https://this-or-that-machine-server.noshado.ws/get-all-pair-ids?key={API_KEY}')
        if response.status_code != 200:
            print(f"Failed to get IDs from API: {response.status_code}")
            return
            
        pair_ids = response.json()
        base_url = "https://ykqtmmyiqcezkfafikuq.supabase.co/storage/v1/object/public/images/"
        
        # Create images directory if it doesn't exist
        if not os.path.exists("images"):
            os.makedirs("images")
            
        # Get list of existing files
        existing_files = set(os.listdir("images"))
        
        # Download missing images
        for pair_id in pair_ids:
            for suffix in ['1', '2']:
                filename = f"{pair_id:05d}_{suffix}.jpg"
                if filename not in existing_files:
                    url = urljoin(base_url, filename)
                    print(f"Downloading {filename}...")
                    try:
                        img_response = requests.get(url)
                        if img_response.status_code == 200:
                            with open(os.path.join("images", filename), 'wb') as f:
                                f.write(img_response.content)
                            print(f"Successfully downloaded {filename}")
                        else:
                            print(f"Failed to download {filename}: {img_response.status_code}")
                    except Exception as e:
                        print(f"Error downloading {filename}: {e}")
                        
    except Exception as e:
        print(f"Error in download_missing_images: {e}")

def get_pair_id(filename):
    """Extract pair ID from filename (e.g., '00384_1.jpg' -> '00384')"""
    match = re.match(r'(\d+)_[12]\.jpg', filename)
    return match.group(1) if match else None

def organize_image_pairs():
    """Organize images into pairs"""
    global image_pairs
    
    # Create a dictionary to group images by pair ID
    pair_dict = {}
    
    for file in os.listdir("images"):
        if file.endswith('.jpg'):
            pair_id = get_pair_id(file)
            if pair_id:
                if pair_id not in pair_dict:
                    pair_dict[pair_id] = [None, None]
                # Determine if it's image 1 or 2 based on the suffix
                idx = 0 if file.endswith('_1.jpg') else 1
                pair_dict[pair_id][idx] = os.path.join("images", file)
    
    # Convert dictionary to list of pairs, only including complete pairs
    image_pairs = []
    for pair_id, paths in pair_dict.items():
        if paths[0] and paths[1]:  # Only include pairs where both images exist
            image_pairs.append(paths)
    
    # Sort pairs by ID first (for consistent initial order)
    image_pairs.sort(key=lambda x: get_pair_id(os.path.basename(x[0])))
    
    # Then shuffle the pairs
    random.shuffle(image_pairs)
    
    print(f"Found {len(image_pairs)} complete image pairs")

def load_current_pair():
    """Load both images of the current pair"""
    global current_images, current_pair_index, image_pairs
    
    if not image_pairs:
        # Create a simple blank image with text
        current_images = [
            pygame.Surface((screen_width//2, screen_height)),
            pygame.Surface((screen_width//2, screen_height))
        ]
        for img in current_images:
            img.fill((0, 0, 0))
            font = pygame.font.Font(None, 36)
            text = font.render("No image pairs found", True, (255, 255, 255))
            text_rect = text.get_rect(center=(screen_width//4, screen_height//2))
            img.blit(text, text_rect)
        return
    
    try:
        # Clear any previously loaded images
        current_images = [None, None]
        
        # Load both images of the current pair
        print(f"Loading pair {current_pair_index + 1}/{len(image_pairs)}")
        for i, img_path in enumerate(image_pairs[current_pair_index]):
            current_images[i] = pygame.image.load(img_path).convert()
        
    except Exception as e:
        print(f"Error loading image pair: {e}")
        # Create error images
        current_images = [
            pygame.Surface((screen_width//2, screen_height)),
            pygame.Surface((screen_width//2, screen_height))
        ]
        for i, img in enumerate(current_images):
            img.fill((0, 0, 0))
            font = pygame.font.Font(None, 36)
            text = font.render(f"Error loading image {i+1}", True, (255, 0, 0))
            text_rect = text.get_rect(center=(screen_width//4, screen_height//2))
            img.blit(text, text_rect)

def display_current_pair():
    """Display the current pair of images side by side"""
    global screen, current_images
    
    if not current_images[0] or not current_images[1]:
        load_current_pair()
    
    # Fill the screen with black first
    screen.fill((0, 0, 0))
    
    # Calculate dimensions for each image
    half_width = screen_width // 2
    
    # Process and display each image
    for i, img in enumerate(current_images):
        # Get the current image dimensions
        img_width, img_height = img.get_size()
        
        # Calculate scale factor to fit half screen while preserving aspect ratio
        scale_factor = min(half_width / img_width, screen_height / img_height)
        
        # Scale the image
        new_width = int(img_width * scale_factor)
        new_height = int(img_height * scale_factor)
        
        try:
            # Use smoothscale for better quality
            scaled_image = pygame.transform.smoothscale(img, (new_width, new_height))
        except:
            # Fallback to regular scale if smoothscale fails
            scaled_image = pygame.transform.scale(img, (new_width, new_height))
        
        # Calculate position to center the image in its half of the screen
        x_pos = i * half_width + (half_width - new_width) // 2
        # Move images down
        y_pos = (screen_height - new_height) // 2 + 40
        
        # Draw the image
        screen.blit(scaled_image, (x_pos, y_pos))
    
    # Update display
    pygame.display.flip()

def next_pair():
    """Switch to the next pair"""
    global current_pair_index, image_pairs, current_images
    
    if not image_pairs:
        return
    
    # Free current images memory    
    current_images = [None, None]
    
    # Get a random index different from the current one
    new_index = current_pair_index
    while new_index == current_pair_index and len(image_pairs) > 1:
        new_index = random.randint(0, len(image_pairs) - 1)
    
    current_pair_index = new_index
    command_queue.put("display")

def previous_pair():
    """Switch to the previous pair"""
    global current_pair_index, image_pairs, current_images
    
    if not image_pairs:
        return
    
    # Free current images memory
    current_images = [None, None]
    
    # Get a random index different from the current one
    new_index = current_pair_index
    while new_index == current_pair_index and len(image_pairs) > 1:
        new_index = random.randint(0, len(image_pairs) - 1)
    
    current_pair_index = new_index
    command_queue.put("display")

def find_local_images():
    """Find all images in the images/ directory and organize them into pairs"""
    global image_pairs
    
    print("Finding local images...")
    
    # Create images directory if it doesn't exist
    if not os.path.exists("images"):
        os.makedirs("images")
        print("Created images/ directory. Please put your images there and restart.")
        return
    
    # Download any missing images first
    download_missing_images()
    
    # Organize images into pairs
    organize_image_pairs()

def monitor_buttons():
    """Monitor GPIO button states in a separate thread"""
    global running, button1_previous, button2_previous, last_button_press_time
    
    print(f"Monitoring GPIO pins {button1_pin} and {button2_pin}")
    
    while running:
        try:
            # Read current button states
            button1_current = GPIO.input(button1_pin)
            button2_current = GPIO.input(button2_pin)
            
            current_time = time.time()
            # Only process button presses if enough time has passed (debouncing)
            if current_time - last_button_press_time >= debounce_time:
                # Check if button1 was just pressed (transition from 0 to 1)
                if button1_current == 1 and button1_previous == 0:
                    print("Button 1 pressed - Next pair")
                    # Use high priority for faster response
                    command_queue.put("next", block=False)
                    last_button_press_time = current_time
                    
                # Check if button2 was just pressed (transition from 0 to 1)
                if button2_current == 1 and button2_previous == 0:
                    print("Button 2 pressed - Previous pair")
                    # Use high priority for faster response
                    command_queue.put("previous", block=False)
                    last_button_press_time = current_time
            
            # Update previous states
            button1_previous = button1_current
            button2_previous = button2_current
            
            # Shorter delay for faster button checks
            time.sleep(0.05)
        except Exception as e:
            print(f"Error in button monitoring thread: {e}")
            time.sleep(0.5)  # Shorter delay on error

def preload_next_images():
    """Preload next and previous images in the background to speed up navigation"""
    global image_pairs, current_pair_index
    
    if not image_pairs or len(image_pairs) <= 1:
        return
    
    # Calculate indexes of next and previous images
    next_idx = (current_pair_index + 1) % len(image_pairs)
    prev_idx = (current_pair_index - 1) % len(image_pairs)
    
    # Try to load these images in the background to have them in file cache
    try:
        # Just open and close the file to have it cached by the system
        with open(image_pairs[next_idx][0], 'rb') as f:
            pass
        with open(image_pairs[next_idx][1], 'rb') as f:
            pass
        with open(image_pairs[prev_idx][0], 'rb') as f:
            pass
        with open(image_pairs[prev_idx][1], 'rb') as f:
            pass
    except Exception:
        pass  # Ignore any errors in preloading

def main():
    global screen, running, screen_width, screen_height, current_pair_index
    
    # Initialize pygame with only the modules we need
    pygame.display.init()
    pygame.font.init()
    
    # Hide mouse cursor
    pygame.mouse.set_visible(False)
    
    # Get the current display size
    info = pygame.display.Info()
    screen_width = info.current_w
    screen_height = info.current_h
    
    # Try to set up the display in fullscreen mode
    try:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        screen_width = screen.get_width()
        screen_height = screen.get_height()
        print(f"Display initialized at {screen_width}x{screen_height}")
    except Exception as e:
        print(f"Error setting fullscreen mode: {e}")
        # Fallback to a smaller resolution if fullscreen fails
        screen_width = 640
        screen_height = 480
        screen = pygame.display.set_mode((screen_width, screen_height))
        print(f"Fallback display initialized at {screen_width}x{screen_height}")
    
    pygame.display.set_caption("RPi Image Pair Viewer")
    
    # Find and organize local images
    find_local_images()
    
    # Set a random initial pair index
    if image_pairs:
        current_pair_index = random.randint(0, len(image_pairs) - 1)
        print(f"Starting with random pair {current_pair_index + 1}/{len(image_pairs)}")
    
    # Start the button monitoring thread
    button_thread = threading.Thread(target=monitor_buttons)
    button_thread.daemon = True
    button_thread.start()
    
    # Display the first pair
    load_current_pair()
    display_current_pair()
    
    # Start preloading neighboring images
    preload_thread = threading.Thread(target=preload_next_images)
    preload_thread.daemon = True
    preload_thread.start()
    
    # Main loop
    try:
        while running:
            # Process events quickly with minimal delay
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                        running = False
                    elif event.key == pygame.K_RIGHT or event.key == pygame.K_n:
                        next_pair()
                    elif event.key == pygame.K_LEFT or event.key == pygame.K_p:
                        previous_pair()
                    elif event.key == pygame.K_r:
                        # Reload image list
                        image_pairs.clear()
                        find_local_images()
                        current_pair_index = 0
                        load_current_pair()
                        display_current_pair()
                    elif event.key == pygame.K_f:
                        # Toggle fullscreen (might not work on all platforms)
                        pygame.display.toggle_fullscreen()
            
            # Check the command queue (non-blocking) with minimal delay
            try:
                command = command_queue.get_nowait()
                if command == "next":
                    next_pair()
                elif command == "previous":
                    previous_pair()
                elif command == "display":
                    load_current_pair()
                    display_current_pair()
                    # After displaying, start preloading the next ones for faster response
                    preload_thread = threading.Thread(target=preload_next_images)
                    preload_thread.daemon = True
                    preload_thread.start()
                command_queue.task_done()
            except queue.Empty:
                pass  # No commands in the queue
            
            # Very short delay to keep the CPU from maxing out
            # but still ensure quick button response
            time.sleep(0.01)
    
    except KeyboardInterrupt:
        print("\nExiting...")
    
    except Exception as e:
        print(f"Error in main loop: {e}")
    
    finally:
        # Clean up
        running = False
        pygame.quit()
        GPIO.cleanup()
        print("Cleanup complete")

if __name__ == "__main__":
    main()
