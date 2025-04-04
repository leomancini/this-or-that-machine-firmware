import pygame
import requests
import io
import sys
import os
from urllib.parse import urlparse

def display_image_fullscreen(image_url):
    # Initialize pygame
    pygame.init()
    
    # Hide mouse cursor
    pygame.mouse.set_visible(False)
    
    # Get the screen info
    screen_info = pygame.display.Info()
    screen_width = screen_info.current_w
    screen_height = screen_info.current_h
    
    # Set up the display
    screen = pygame.display.set_mode((screen_width, screen_height), pygame.FULLSCREEN)
    pygame.display.set_caption("Fullscreen Image Viewer")
    
    try:
        # Download the image
        response = requests.get(image_url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        # Load the image from the response content
        image_file = io.BytesIO(response.content)
        image = pygame.image.load(image_file)
        
        # Scale the image to fit the screen while maintaining aspect ratio
        img_width, img_height = image.get_size()
        scale_factor = min(screen_width / img_width, screen_height / img_height)
        new_width = int(img_width * scale_factor)
        new_height = int(img_height * scale_factor)
        scaled_image = pygame.transform.scale(image, (new_width, new_height))
        
        # Calculate position to center the image
        x_pos = (screen_width - new_width) // 2
        y_pos = (screen_height - new_height) // 2
        
        # Fill the screen with black
        screen.fill((0, 0, 0))
        
        # Draw the image on the screen
        screen.blit(scaled_image, (x_pos, y_pos))
        pygame.display.flip()
        
        # Main loop
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                        running = False
    
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        # Quit pygame
        pygame.quit()
        

if __name__ == "__main__":
    # Check if URL is provided as command line argument
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        # Default URL if none provided
        url = "https://source.unsplash.com/random/1920x1080"
        print(f"No URL provided, using random image from Unsplash")
    
    print(f"Displaying image from: {url}")
    display_image_fullscreen(url)
