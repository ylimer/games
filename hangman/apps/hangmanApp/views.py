from django.shortcuts import render, redirect, HttpResponse
from django.http import HttpResponseRedirect, JsonResponse
from django.core.urlresolvers import reverse
import requests
import random
import re

# index(): display index page
def index(request):
    if 'secret' in request.session:
        return HttpResponseRedirect(reverse('play_url'))

    return render(request, 'index.html')

# start(): endpoint for /start post action 
# set up game, storing session variables
def start(request):
    if request.method == 'POST':
        request.session['name'] = request.POST['name']
        request.session['level'] = request.POST['level']
        if 'prepopulate' in request.POST:
            request.session['prepopulate'] = request.POST['prepopulate']

        return HttpResponseRedirect(reverse('play_url'))
    else:
        return JsonResponse({ "nothing to see": "try again" })

# play(): displays the game, the form for guessing and guesses so far
def play(request):
    if 'name' not in request.session:
        return HttpResponseRedirect(reverse('index_url'))

    if 'secret' not in request.session:
        initialize(request)

    context = process(request)
    return render(request, 'game/play.html', context)

# initialize(): helper function to initialize session variables
def initialize(request):
    request.session['api_attempt'] = 0

    # get the word
    secret = get_word(request)
    if secret == 'ERROR: API GET':
        return JsonResponse({ "ERROR": "API GET" })
    else:
        request.session['secret'] = secret

    request.session['guess_count'] = 6 # no. of guesses allowed
    request.session['char_dict'] = {}  # dictionary of characters in secret word
    request.session['missed'] = {}     # dictionary of missed characters
    request.session['word'] = "_" * len(request.session['secret']) # the word to be displayed, initially underscores

    # turn on the secret word for development
    if request.session['name'] == 'Bob':
        request.session['debug'] = True

    # store the characters of the word as keys in a dictionary
    # the values are lists of character positions in the word
    char_dict = {}
    for index, char in enumerate(request.session['secret']):
        if char in char_dict:
            char_dict[char].append(index)
        else:
            char_dict[char] = [index]
    request.session['char_dict'] = char_dict


    # prepopulate a random character and its other occurrences if option turned on
    # make sure we have more than 1 unique character in the secret word (in case the word is all the same letter)
    if 'prepopulate' in request.session and len(char_dict.keys()) > 1:
        prepopulate = random.choice(char_dict.keys()) # pick one from unique keys
        length_of_reveal = len(char_dict[prepopulate])
        print "key to be revealed: ", length_of_reveal, ", length: ", length_of_reveal
        # we don't want to give everything away, set a threshold
        while length_of_reveal/len(request.session['secret']) > .50:
            prepopulate = random.choice(char_dict.keys())
            length_of_reveal = len(char_dict[prepopulate])

        # reveal the occurrences of the randomly chosen character
        progress_list = list(request.session['word'])
        for position in request.session['char_dict'][prepopulate]:
            progress_list[position] = prepopulate
        request.session['word'] = ''.join(progress_list)


# get_word(level): request words from api
# returns a word from randomized list
def get_word(request):
    level = request.session['level']
    url = "http://linkedin-reach.hagbpyjegb.us-west-2.elasticbeanstalk.com/words?"
    url += "difficulty=" + level + "&minLength=4" + "&count="

    # brand new word_dictionary. first time set up
    if 'word_dictionary' not in request.session:
        request.session['word_dictionary'] = {}

    # set up word_dictionary for each level. make request to api and randomize list
    if level not in request.session['word_dictionary']:
        print "go to api for level", level 
        wordlist = requests.get(url).content.split("\n")
        random.shuffle(wordlist)
        request.session['word_dictionary'][level] = wordlist

    print "dictionary: ", len(request.session['word_dictionary'][level])

    if len(request.session['word_dictionary'][level]) > 20:
        # pop one word from randomized list
        word = request.session['word_dictionary'][level].pop()
        request.session['api_attempt'] = 0
    elif request.session['api_attempt'] < 4:
        # attempt to call the api again if we don't get a word list or we are about to exhaust our list
        request.session['api_attempt'] += 1 
        if level in request.session['word_dictionary']:
            del request.session['word_dictionary'][level]
        word = get_word(request)
    else:
        word = "ERROR: API GET"

    print "secret: " + word

    return word

# guess(): endpoint for /guess post action
# determine game outcome from guess
# deduct the guess count if character not in the secret word
def guess(request):
    if request.method == 'POST':
        guess = request.POST['guess'].lower()

        # check for valid characters 
        regex = re.escape(guess) 
        if not re.search(r'[a-z]', regex):
            return JsonResponse({ "error": "Special characters and numbers are not valid." }) 

        # check to see if letter already guessed from the missed list and correct guesses
        if guess in request.session['missed'] or re.search(regex, request.session['word']): 
            return JsonResponse({ "error": "You have already guessed that." }) 

        missed = None
        occurrences = None
        # guessing a word
        if len(guess) > 1:
            # correct word guess
            if guess == request.session['secret']:
                request.session['word'] = guess
            else:
                missed = "Your guess '{}' is incorrect." .format(guess)
        # guessing a character
        else: 
            # correct character guess
            if guess in request.session['char_dict']:
                times = "times." if len(request.session['char_dict'][guess]) > 1 else "time."
                occurrences = "Character '{}' appears {} {}" .format(guess, str(len(request.session['char_dict'][guess])), times)
                # reveal occurrence of the correct character guess in the word
                progress_list = list(request.session['word'])
                for position in request.session['char_dict'][guess]:
                    progress_list[position] = guess
                request.session['word'] = ''.join(progress_list)

            else:
                missed = "Character '{}' is not part of the word." .format(guess)

        # add the guess to dictionary of misses and decrement count
        if missed:
            request.session['missed'][guess] = 1
            request.session['guess_count'] -= 1

        context = process(request)
        context['missed'] = missed 
        context['occurrences'] = occurrences
     
        return JsonResponse(context)
    else:
        return JsonResponse({ "nothing to see": "try again" })

# process(): helper function
# takes in request as input
# returns context dictionary to render in the display board
def process(request):
    # determine win
    win = False
    if request.session['word'] == request.session['secret'] and request.session['guess_count'] > 0:
        win = True

    # determine if game is over
    game_over = False
    if win or (not win and request.session['guess_count'] <= 0):
        game_over = True

    context = {
        'length'         : len(request.session['secret']),
        'word'           : ' '.join(request.session['word']),
        'guess_count'    : request.session['guess_count'],
        'missed_guesses' : ' '.join(sorted(request.session['missed'])),
        'win'            : win,
        'game_over'      : game_over,
    }

    # reveal the secret word
    if game_over:
        context['secret'] = request.session['secret']

    return context

# get_count(): return the current guess count
def get_count(request):
    if 'secret' not in request.session:
        return HttpResponseRedirect(reverse('index_url'))

    return JsonResponse({ 'guess_count': request.session['guess_count'] });

# reset(): resets session variables
def reset(request):
    if 'name' not in request.session:
        return HttpResponseRedirect(reverse('index_url'))

    try:
        for key in ['secret', 'word', 'guess_count', 'missed', 'char_dict']:
            del request.session[key]
    except KeyError, e:
        print "Oops!  No such key", e

    return HttpResponseRedirect(reverse('play_url'))

# logout()
def logout(request):
    if 'name' not in request.session:
        return HttpResponseRedirect(reverse('index_url'))

    try:
        for key in ['secret', 'word', 'guess_count', 'missed', 'char_dict', 'name', 'level', 'debug', 'prepopulate']:
            del request.session[key]
    except Exception, e:
        print "Oops! Exception", e

    return HttpResponseRedirect(reverse('index_url'))

# leaderboard(): show scores and your performance
def leaderboard(request):
    if 'name' not in request.session:
        return HttpResponseRedirect(reverse('index_url'))

    return render(request, 'dashboard/leaderboard.html')

# settings(): options to choose theme, customize word bank, choose number of guesses
def settings(request):
    if 'name' not in request.session:
        return HttpResponseRedirect(reverse('index_url'))

    return render(request, 'dashboard/settings.html')
