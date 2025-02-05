import obspython
import math
import time
import typing
import contextlib
import pathlib
import re
import datetime
import threading
import dataclasses

# typing helper just so we can hint what type we are dealing with

class obs_source:
    pass

class obs_weak_source:
    pass

class obs_scene:
    pass

class obs_sceneitem:
    pass

class obs_signal_handler:
    pass

obs_source_list = list[obs_source]

class obs_data:
    pass

class obs_data_item:
    pass

class obs_data_array:
    pass

class obs_hotkey_id:
    pass

class obs_properties:
    pass

class obs_property:
    pass

_T = typing.TypeVar('T')

class ObsTools:

    SOURCE_TYPE_ID_IMAGE = "image_source"

    @staticmethod
    def get_source_name_list( filter : typing.Callable[[obs_source],bool] = None ) -> list[str]:
        with ObsTools.access_sources() as sources:
            return [obspython.obs_source_get_name(source) for source in sources if filter is None or filter(source)]
    
    @staticmethod
    @contextlib.contextmanager
    def access_current_scene() -> typing.Generator[obs_source,None,None]:
        return ObsTools.scope_source_ref( lambda: obspython.obs_frontend_get_current_scene() )
    
    @staticmethod
    @contextlib.contextmanager
    def access_sources() -> typing.Generator[obs_source_list,None,None]:
        return ObsTools.scope_source_ref_list( lambda: obspython.obs_enum_sources() )

    @staticmethod
    @contextlib.contextmanager
    def access_new_data() -> typing.Generator[obs_data,None,None]:
        return ObsTools.scope_data_ref( lambda: obspython.obs_data_create() )

    @staticmethod
    @contextlib.contextmanager
    def access_object_in_data( data : obs_data, name : str ) -> typing.Generator[obs_data,None,None]:
        return ObsTools.scope_data_ref( lambda: obspython.obs_data_get_obj( data, name ) )

    @staticmethod
    @contextlib.contextmanager
    def access_data_item_as_object( data_item : obs_data_item ) -> typing.Generator[obs_data,None,None]:
        return ObsTools.scope_data_ref( lambda: obspython.obs_data_item_get_obj( data_item ) )

    @staticmethod
    @contextlib.contextmanager
    def access_array_in_data( data : obs_data, name : str ) -> typing.Generator[obs_data_array,None,None]:
        return ObsTools.scope_data_array_ref( lambda: obspython.obs_data_get_array( data, name ) )

    @staticmethod
    @contextlib.contextmanager
    def access_item_of_data_array( data_array : obs_data_array, index : int ) -> typing.Generator[obs_data,None,None]:
         return ObsTools.scope_data_ref( lambda: obspython.obs_data_array_item( data_array, index ) )

    @staticmethod
    @contextlib.contextmanager
    def access_data_item_as_array( data_item : obs_data_item ) -> typing.Generator[obs_data_array,None,None]:
         return ObsTools.scope_data_array_ref( lambda: obspython.obs_data_item_get_array( data_item ) )

    @staticmethod
    @contextlib.contextmanager
    def access_hotkey_save( hotkey_id : obs_hotkey_id ) -> typing.Generator[obs_data_array,None,None]:
        return ObsTools.scope_data_array_ref( lambda: obspython.obs_hotkey_save( hotkey_id ) )

    @staticmethod
    @contextlib.contextmanager
    def access_source_settings( source : obs_source ) -> typing.Generator[obs_data,None,None]:
        return ObsTools.scope_data_ref( lambda: obspython.obs_source_get_settings( source ) )

    @staticmethod
    @contextlib.contextmanager
    def access_weak_source( weak_source : obs_weak_source ) -> typing.Generator[obs_source,None,None]:
        return ObsTools.scope_source_ref( lambda: obspython.obs_weak_source_get_source( weak_source ) )

    @staticmethod
    @contextlib.contextmanager
    def access_source_filter_by_name( source : obs_source, name : str ) -> typing.Generator[obs_source,None,None]:
        return ObsTools.scope_source_ref( lambda: obspython.obs_source_get_filter_by_name( source, name ) )

    @staticmethod
    def save_sources() -> None:
        @contextlib.contextmanager
        def get_sources_save_data():
            return ObsTools.scope_data_array_ref( lambda: obspython.obs_save_sources() )
        with get_sources_save_data() as _:
            pass # OBS saved all sources internally as a side effect of obtaining the data
    
    @staticmethod
    @contextlib.contextmanager
    def save_source( source : obs_source ) -> typing.Generator[obs_data,None,None]:
        return ObsTools.scope_data_ref( lambda: obspython.obs_save_source( source ) )

    @staticmethod
    @contextlib.contextmanager
    def access_scenes() -> typing.Generator[obs_source_list,None,None]:
        return ObsTools.scope_source_ref_list( lambda: obspython.obs_frontend_get_scenes() )

    @staticmethod
    def scope_source_ref( ctor : typing.Callable[[],obs_source] ) -> typing.Generator[obs_source,None,None]:
        return ObsTools.resource_scope_as_generator( ctor, lambda source: obspython.obs_source_release(source)  )

    @staticmethod
    def scope_source_ref_list( ctor : typing.Callable[[],obs_source_list] ) -> typing.Generator[obs_source_list,None,None]:
        return ObsTools.resource_scope_as_generator( ctor, lambda source_list: obspython.source_list_release(source_list)  )

    @staticmethod
    def scope_data_ref( ctor : typing.Callable[[],obs_data] ) -> typing.Generator[obs_data,None,None]:
        return ObsTools.resource_scope_as_generator( ctor, lambda data: obspython.obs_data_release(data)  )
    
    @staticmethod
    def scope_data_array_ref( ctor : typing.Callable[[],obs_data_array] ) -> typing.Generator[obs_data_array,None,None]:
        return ObsTools.resource_scope_as_generator( ctor, lambda array: obspython.obs_data_array_release(array)  )

    @staticmethod
    def resource_scope_as_generator( ctor : typing.Callable[[],_T], dtor : typing.Callable[[_T],None] ) -> typing.Generator[_T,None,None]:
        """Compatible with @contextlib.contextmanager"""
        resource = None
        try:
            resource = ctor()
            yield resource
        finally:
            if resource is not None:
                dtor( resource )

    @staticmethod
    def transmute_data_to_dict( data : obs_data ) -> dict:
        """
        Transmute OBS data to dict (destructively) (and memory leakily).
        """
        retval = dict()

        def process_item( item : obs_data_item ):
            item_name = obspython.obs_data_item_get_name( item )
            item_type = obspython.obs_data_item_gettype( item )
            match item_type:
                case 0: # Null
                    retval[item_name] = None
                case 1: # String
                    retval[item_name] = obspython.obs_data_item_get_string( item )
                case 2: # Number
                    item_num_type = obspython.obs_data_item_numtype( item )
                    match item_num_type:
                        case 0:
                            retval[item_name] = "Invalid number"
                        case 1:
                            retval[item_name] = obspython.obs_data_item_get_int( item )
                        case 2:
                            retval[item_name] = obspython.obs_data_item_get_double( item )
                        case _:
                            retval[item_name] = "Unknown number type"
                case 3: # Bool
                    retval[item_name] = obspython.obs_data_item_get_bool( item )
                case 4: # Object
                    with ObsTools.access_data_item_as_object( item ) as item_data:
                        retval[item_name] = ObsTools.transmute_data_to_dict( item_data )
                case 5: # Array
                    with ObsTools.access_data_item_as_array( item ) as obs_array:
                        count = obspython.obs_data_array_count( obs_array )
                        array = []
                        for i in range( 0, count ):
                            with ObsTools.access_item_of_data_array( obs_array, i ) as array_item:
                                array.append( ObsTools.transmute_data_to_dict( array_item ) )
                        retval[item_name] = array
                case _:
                    print( f"Unknown data item type for item {item_name}: {item_type}")
        
        while True:
            try:
                first = obspython.obs_data_first( data )
                if first is None:
                    break
                name = obspython.obs_data_item_get_name( first )
                process_item( first )
                obspython.obs_data_erase( data, name )
            finally:
                pass # This just leaks a data item reference. It should be freed using obspython.obs_data_item_release() which is, sadly, incompatible with python
        
        return retval

class Synchronized(typing.Generic[_T]):

    _value : _T
    _lock : threading.RLock

    def __init__(self, value : _T):
        self._value = value
        self._lock = threading.RLock()
    
    def lock(self) -> "LockContext[_T]":
        return LockContext(self)
    
    def set(self, value : _T) -> None:
        with self.lock():
            self._value = value

class LockContext(typing.Generic[_T]):

    _synchronized : Synchronized[_T]

    def __init__(self, _synchronized : Synchronized[_T] ):
        self._synchronized = _synchronized

    def __enter__(self):
        self._synchronized._lock.acquire()
        return self._synchronized._value

    def __exit__(self, type, value, traceback):
        return self._synchronized._lock.release()

class PropertyBinding(typing.Protocol):
    
    def define( self, properties : obs_properties ):
        """"""
    
    def default( self, settings : obs_data ):
        """"""
    
    def update( self, settings : obs_data ):
        """"""

class SourceProperty(PropertyBinding):

    name : str = ""

    _LABEL : str
    _DESCRIPTION : str | None = None
    _KEY : str
    _property : obs_property

    def define( self, properties : obs_properties ):
        self._property = obspython.obs_properties_add_list(properties, self._KEY, self._LABEL, obspython.OBS_COMBO_TYPE_LIST, obspython.OBS_COMBO_FORMAT_STRING)
        obspython.obs_properties_add_text(properties, self._KEY, self._LABEL, obspython.OBS_TEXT_DEFAULT)
        if self._DESCRIPTION is not None:
            obspython.obs_property_set_long_description( self._property, self._DESCRIPTION )
        self.refresh_source_options()
    
    def default( self, settings : obs_data ):
        obspython.obs_data_set_default_string(settings, self._KEY, "")
    
    def update( self, settings : obs_data ):
        self.name = obspython.obs_data_get_string( settings, self._KEY )
    
    def refresh_source_options( self ):
        obspython.obs_property_list_clear(self._property)
        obspython.obs_property_list_add_string(self._property, "", "") # Include empty option
        for potential_source_name in ObsTools.get_source_name_list( filter=lambda s: self.is_compatible_source(s) ):
            obspython.obs_property_list_add_string(self._property, potential_source_name, potential_source_name)    

    def is_compatible_source( self, _ : obs_source ):
        return True

class DisplaySourcePropertyBinding(SourceProperty):

    def __init__( self ):
        self._LABEL = "Display source (image)"
        self._DESCRIPTION = None
        self._KEY = "display_source"
    
    def is_compatible_source( self, source : obs_source ):
        #print( f"{obspython.obs_source_get_name( source )} - {obspython.obs_source_get_id( source )}" )
        return obspython.obs_source_get_id( source ) == ObsTools.SOURCE_TYPE_ID_IMAGE 

class CaptureSourcePropertyBinding(SourceProperty):
    
    def __init__( self ):
        self._LABEL = "Capture source (Not hidden!)"
        self._DESCRIPTION = "NOTE: obs-screenshot-plugin is used to take snapshots periodically and, as of this writing, it does not like (crashes) when the source is hidden. It's OK to move it off-screen."
        self._KEY = "capture_source"

class SnapshotFolderPropertyBinding(PropertyBinding):

    path : str = ""

    _LABEL = "Snapshot work folder"
    _DESCRIPTION = "Working folder where snapshots will be saved. The snapshots are only kept around only as long as necessary for display."
    _KEY = "snapshot_path"

    def define( self, properties : obs_properties ):
        prop = obspython.obs_properties_add_path( properties, self._KEY, self._LABEL, type=obspython.OBS_PATH_DIRECTORY, filter=None, default_path="" )
        obspython.obs_property_set_long_description( prop, self._DESCRIPTION )
    
    def default( self, settings : obs_data ):
        obspython.obs_data_set_default_string(settings, self._KEY, "")
    
    def update( self, settings : obs_data ):
        self.path = obspython.obs_data_get_string( settings, self._KEY )

class IntSliderPropertyBinding(PropertyBinding):
    
    value : int | None = None

    _label : str
    _description : str
    _key : str

    _min : int
    _max : int
    _step : int
    _default : int

    def __init__( self, label : str, description : str | None, key : str, min : int, max : int, step : int, default : int ):
        self._label = label
        self._description = description
        self._key = key

        self._min = min
        self._max = max
        self._step = step
        self._default = default
        self.value = default

    def define( self, properties : obs_properties ):
        prop = obspython.obs_properties_add_int_slider( properties, self._key, self._label, min=self._min, max=self._max, step=self._step )
        if self._description is not None:
            obspython.obs_property_set_long_description( prop, self._description )
    
    def default( self, settings : obs_data ):
        obspython.obs_data_set_default_int(settings, self._key, self._default)
    
    def update( self, settings : obs_data ):
        self.value = obspython.obs_data_get_int( settings, self._key )

@dataclasses.dataclass
class _SnapshotInfo:
    path : pathlib.Path
    timestamp : datetime

class _ConcurrentSnapshotLogic:
    """Snapshot file logic that is vulnerable to race conditions."""
    _protected_snapshots : list[_SnapshotInfo]
    
    def __init__( self ):
        self._protected_snapshots = []

    def get_protected_snapshots( self ) -> list[_SnapshotInfo]:
        return self._protected_snapshots.copy() # avoid accidental modification outside lock
    
    def set_protected_snapshots( self, snapshots : list[_SnapshotInfo] ) -> None:
        self._protected_snapshots = snapshots.copy() # avoid accidental modification outside lock

    def select_snapshot( self, snapshots : list[_SnapshotInfo], look_behind_seconds : float ) -> _SnapshotInfo | None:
        # The main vulnerability is that pop_snapshot() could read now() first but not act on it prior to delete_old_snapshots() reading a slightly higher value of now()
        # which can lead to deletion of the only snapshot pop_snapshot() deems applicable due to lower value of now().
        now = datetime.datetime.now()
        look_behind = datetime.timedelta( seconds=look_behind_seconds )

        def is_old_enough( timestamp : datetime.datetime ) -> bool:
            return (now - timestamp) >= look_behind

        applicable_snapshots = [ snapshot for snapshot in snapshots if is_old_enough(snapshot.timestamp) ]
        
        best_snapshot = max( applicable_snapshots, key=lambda snapshot: snapshot.path, default=None ) # we want the newest, therefore max by datetime
        return best_snapshot

class SnapshotPopper:
    """OBS script that pops a snapshot of the selected source"""

    _GUID = "18C64899-CCD4-484C-AB38-4E51596C4FDB"
    _ANNOTATED_GUID = f"Snapshot-Popper-{_GUID}"

    _display_source : obs_weak_source = None
    _display_source_visible : bool = False
    _display_item_original_visibility : bool | None = None

    _capture_source : obs_weak_source = None
    _SNAPSHOT_FILTER_INSTANCE_NAME = "Screenshot filter (Snapshot Popper)"

    _POP_SNAPSHOT_LABEL = "Pop snapshot"
    _POP_SNAPSHOT_KEY = "pop_snapshost"
    _POP_SNAPSHOT_GUID = f"{_ANNOTATED_GUID}-{_POP_SNAPSHOT_KEY}"
    _pop_snapshot_hotkey_id : obs_hotkey_id = obspython.OBS_INVALID_HOTKEY_ID
    _last_pop_time : float = math.nan

    _display_source_prop : DisplaySourcePropertyBinding # name of the source used to display the snapshot
    _capture_source_prop : CaptureSourcePropertyBinding # name of the source used to capture the snapshots
    _snapshot_folder_prop : SnapshotFolderPropertyBinding
    _pop_duration_ms_prop : IntSliderPropertyBinding
    _pop_look_behind_ms_prop : IntSliderPropertyBinding
    _snapshot_frequency_ms_prop : IntSliderPropertyBinding

    _on_snapshot_hotkey : typing.Callable
    _on_tick : typing.Callable

    _property_bindings : list[PropertyBinding]

    _old_snapshot_deleter_thread : threading.Thread = None
    _old_snapshot_deleter_thread_shutdown_pending : bool = False
    _concurrent_snapshot_logic : Synchronized[_ConcurrentSnapshotLogic]

    _screenshot_filter : obs_source | None = None

    def __init__( self ):
        self._property_bindings = list()
        
        self._snapshot_folder_prop = SnapshotFolderPropertyBinding()
        self._property_bindings.append( self._snapshot_folder_prop )

        self._pop_duration_ms_prop = IntSliderPropertyBinding( "Pop duration (ms)", None, "pop_duration_ms", min=0, max=30000, step=100, default=5000)
        self._property_bindings.append( self._pop_duration_ms_prop )

        self._pop_look_behind_ms_prop = IntSliderPropertyBinding( "Pop look behind (ms)", "Configure to display snapshot older than the current capture. Useful to prevent popping of undesirable imagery suddenly appearing in the capture as the hotkey is being pressed.", "pop_look_behind_ms", min=0, max=5000, step=100, default=1000)
        self._property_bindings.append( self._pop_look_behind_ms_prop )

        self._snapshot_frequency_ms_prop = IntSliderPropertyBinding( "Snapshot frequency (ms)", "Lower value improves latency at the cost of performance and disk space.", "snapshot_frequency_ms", min=1200, max=5000, step=100, default=1000)
        self._property_bindings.append( self._snapshot_frequency_ms_prop )

        self._display_source_prop = DisplaySourcePropertyBinding()
        self._property_bindings.append( self._display_source_prop )

        self._capture_source_prop = CaptureSourcePropertyBinding()
        self._property_bindings.append( self._capture_source_prop )

        self._on_snapshot_hotkey = lambda pressed: self.pop_snapshot()
        self._on_tick = lambda: self.tick()

        self._concurrent_snapshot_logic = Synchronized(_ConcurrentSnapshotLogic())

    def load( self, settings : obs_data ):
        """Load snapshot popper functionality"""
        self._pop_snapshot_hotkey_id = obspython.obs_hotkey_register_frontend( self._POP_SNAPSHOT_GUID, self._POP_SNAPSHOT_LABEL, self._on_snapshot_hotkey )
        with ObsTools.access_array_in_data( settings, self._POP_SNAPSHOT_KEY ) as hotkey_save_array:
            obspython.obs_hotkey_load(self._pop_snapshot_hotkey_id, hotkey_save_array) # load hotkey settings from persistent storage
        obspython.timer_add( self._on_tick, 100 )

        def delete_old_snapshots_proc():
            while not self._old_snapshot_deleter_thread_shutdown_pending:
                self.delete_old_snapshots()
                time.sleep(1.0)
        
        self._old_snapshot_deleter_thread_shutdown_pending = False
        self._old_snapshot_deleter_thread = threading.Thread( target=delete_old_snapshots_proc )
        self._old_snapshot_deleter_thread.daemon = True
        print( "Starting thread." )
        self._old_snapshot_deleter_thread.start()

    def description( self ):
        return f"""<center><h2>Snapshot Popper</h2></center>
                  <p>Creates a hotkey to display a snapshot from a source for a duration of time. The snapshots are taken continuously.</p>
                  <p>Requires obs-screenshot-plugin.</p>
                  <p>The hotkey can be configured in File → Settings → Hotkeys → \"{self._POP_SNAPSHOT_LABEL}\".</p>"""

    def defaults( self, settings : obs_data ):
        """Set default values of data settings"""
        for property_binding in self._property_bindings:
            property_binding.default( settings )

    def properties( self ):
        """Display properties GUI"""
        properties = obspython.obs_properties_create()

        for property_binding in self._property_bindings:
            property_binding.define( properties )

        def refresh_source_options( _ = None, __ = None ): # Two unused params in OBS button callback
            self._display_source_prop.refresh_source_options()
            self._capture_source_prop.refresh_source_options()
            return True # Apparently, required by OBS button callback
        
        obspython.obs_properties_add_button(properties, "button", "Refresh list of sources", refresh_source_options )

        return properties

    def update( self, settings : obs_data ):
        """Apply settings"""
        self.propagate_configuration( disable=True, remove_filter_on_disable=False ) # There appears to be a bug in the filter causing crashes if it is added/removed frequently

        for property_binding in self._property_bindings:
            property_binding.update( settings )
        
        self.propagate_configuration()

    def save( self, settings : obs_data ):
        with ObsTools.access_hotkey_save( self._pop_snapshot_hotkey_id ) as hotkey_save_array:
            obspython.obs_data_set_array(settings, self._POP_SNAPSHOT_KEY, hotkey_save_array) # save hotkey settings to persistent storage
    
    def unload( self ):
        """Unload the script"""
        print( "Shutting down thread." )
        self._old_snapshot_deleter_thread_shutdown_pending = True
        self._old_snapshot_deleter_thread.join()
        print( "Threat shut down." )

        obspython.obs_hotkey_unregister( self._pop_snapshot_hotkey_id )
        obspython.timer_remove( self._on_tick )
        self.propagate_configuration( disable=True )

        if self._screenshot_filter is not None:
            obspython.obs_source_release( self._screenshot_filter )
            self._screenshot_filter = None

    def pop_snapshot( self ):
        self.propagate_configuration()
        with ObsTools.access_weak_source( self._display_source ) as display_source:
            with self._concurrent_snapshot_logic.lock() as concurrent_snapshot_logic:
                best_snapshot = concurrent_snapshot_logic.select_snapshot( self.get_snapshots(), self._pop_look_behind_ms_prop.value/1000 )
                if best_snapshot is not None:
                    concurrent_snapshot_logic.set_protected_snapshots( [best_snapshot] )
            if display_source is not None and best_snapshot is not None:
                with ObsTools.access_source_settings(display_source) as settings:
                    obspython.obs_data_set_string( settings, "file", str(best_snapshot.path) )
                    obspython.obs_source_update( display_source, settings )
                obspython.obs_sceneitem_set_visible( self.get_scene_item_by_name(self._display_source_prop.name), True )
                self._display_source_visible = True
        self._last_pop_time = time.monotonic()
    
    def should_display_be_visible( self ):
        return self._last_pop_time != math.nan and time.monotonic() < self._last_pop_time + (self._pop_duration_ms_prop.value/1000)

    def get_snapshot_folder( self ) -> pathlib.Path | None:
        if len( self._snapshot_folder_prop.path or "" ) == 0:
            return None
        
        return pathlib.Path( self._snapshot_folder_prop.path )

    def get_snapshots( self ) -> list[_SnapshotInfo]:

        retval = []

        folder = self.get_snapshot_folder()

        if folder is None:
            return retval

        for path in folder.iterdir():
            if not path.is_file():
                continue
            
            match = re.fullmatch( r"(?P<timestamp>[\d]{4}-[\d]{2}-[\d]{2}_[\d]{2}-[\d]{2}-[\d]{2})(_[\d]+.raw)?.png", path.name ) # _<number>.raw gets added to filenames when multiple snapshots occur in the same second
            
            if match is None:
                continue
            
            timestamp = datetime.datetime.strptime( match.group( "timestamp" ), r"%Y-%m-%d_%H-%M-%S" )
            retval.append( _SnapshotInfo(path,timestamp) )
        
        return retval

    def tick( self ):
        should_be_hidden = not self.should_display_be_visible()
        if should_be_hidden and self._display_source_visible: # pop_snapshot() takes care of showing the pop so here we need only to hide it when appropriate
            self._display_source_visible = False
            self.propagate_configuration()
            with ObsTools.access_weak_source( self._display_source ) as display_source:
                if display_source is not None:
                    obspython.obs_sceneitem_set_visible( self.get_scene_item_by_name(self._display_source_prop.name), False )
            # leave the snapshot protected for the hide transition, we can afford an extra snapshot
    
    def delete_old_snapshots( self ):
        # Do not remove anything that might be used now or by future pop_snapshot() calls to avoid concurrency issues.
        
        snapshots = self.get_snapshots()

        with self._concurrent_snapshot_logic.lock() as concurrent_snapshot_logic:
            best_snapshot = concurrent_snapshot_logic.select_snapshot( snapshots, self._pop_look_behind_ms_prop.value / 1000 )
            protected_snapshots = concurrent_snapshot_logic.get_protected_snapshots()

        if best_snapshot is None:
            return

        for snapshot in snapshots:
            if snapshot.path in [protected_snapshot.path for protected_snapshot in protected_snapshots]:
                continue # Protected snapshots are currently displayed so do not delete them.
            
            if snapshot.timestamp >= best_snapshot.timestamp:
                # The best snapshot and newer could be chosen by future pop_snapshot() calls so do not delete them.
                continue
            
            snapshot.path.unlink( missing_ok=True )
 
    def get_scene_item_by_name( self, name ) -> obs_sceneitem:
        """Find a scene item by name"""
        with ObsTools.access_scenes() as scene_sources:
            for scene_source in scene_sources:
                scene_source = obspython.obs_scene_from_source(scene_source)
                retval = obspython.obs_scene_find_source_recursive(scene_source, name)
                if retval is not None:
                    return retval
        return None
    
    def propagate_configuration( self, disable : bool = False, remove_filter_on_disable : bool = True ) -> None:
        with ( ObsTools.access_weak_source( self._display_source ) as display_source,
               ObsTools.access_weak_source( self._capture_source ) as capture_source ):

            if disable:
                updated_display_source = None
                updated_capture_source = None
            else:
                updated_display_source = obspython.obs_sceneitem_get_source( self.get_scene_item_by_name(self._display_source_prop.name) )
                updated_capture_source = obspython.obs_sceneitem_get_source( self.get_scene_item_by_name(self._capture_source_prop.name) )

            if display_source != updated_display_source:
                if display_source is not None:
                    with ObsTools.access_source_settings(display_source) as settings:
                        obspython.obs_data_set_string( settings, "file", "" )
                    obspython.obs_sceneitem_set_visible( self.get_scene_item_by_name(self._display_source_prop.name), self._display_item_original_visibility )
                
                if updated_display_source is not None:
                    updated_display_scene_item = self.get_scene_item_by_name(self._display_source_prop.name)
                    self._display_item_original_visibility = obspython.obs_sceneitem_visible( updated_display_scene_item )
                    obspython.obs_sceneitem_set_visible( updated_display_scene_item, False )
                    self._display_source_visible = False                    

                obspython.obs_weak_source_release( self._display_source )
                self._display_source = obspython.obs_source_get_weak_source( updated_display_source )
            
            if capture_source != updated_capture_source:
                if not disable or remove_filter_on_disable:
                    self.remove_screenshot_filters()
                
                if updated_capture_source is not None and len( self._snapshot_folder_prop.path or "" ) > 0:
                    self.ensure_screenhot_filter_present( updated_capture_source )
                
                obspython.obs_weak_source_release( self._capture_source )
                self._capture_source = obspython.obs_source_get_weak_source( updated_capture_source )

    def update_screenshot_filter( self ) -> obs_source:
        # Screenshot filter configuration example:
        #      "settings": {
        #          "capture_hotkey": [],
        #          "destination_folder": "D:/Workshop/streaming/ChatSnap",
        #          "destination_type": 3.0,
        #          "interval": 2.0,
        #          "raw": false,
        #          "timer": true
        #      },
        # Captured using print( json.dumps( ObsTools.transmute_data_to_dict( filter_data ), sort_keys=True, indent=4 ) )
        with ObsTools.access_new_data() as screenshot_filter_data:
            obspython.obs_data_set_double( screenshot_filter_data, "destination_type", 3.0 )
            obspython.obs_data_set_string( screenshot_filter_data, "destination_folder", self._snapshot_folder_prop.path )
            obspython.obs_data_set_double( screenshot_filter_data, "interval", max( 0.1, self._snapshot_frequency_ms_prop.value / 1000 ) )
            obspython.obs_data_set_bool( screenshot_filter_data, "raw", False )
            obspython.obs_data_set_bool( screenshot_filter_data, "timer", True )

            if self._screenshot_filter is None:
                self._screenshot_filter = obspython.obs_source_create( "screenshot_filter", self._SNAPSHOT_FILTER_INSTANCE_NAME, settings=screenshot_filter_data, hotkey_data=None )
            else:
                obspython.obs_source_update( self._screenshot_filter, screenshot_filter_data )

    def ensure_screenhot_filter_present( self, source : obs_source ) -> None:
        self.update_screenshot_filter()

        for present_filter_name in self.get_screenshot_filter_names_from_source( source ):
            with ObsTools.access_source_filter_by_name( source, present_filter_name ) as present_filter:
                if present_filter == self._screenshot_filter:
                    return # the screenshot filter is already present

        obspython.obs_source_filter_add( source, self._screenshot_filter )
    
    def get_screenshot_filter_names_from_source( self, source : obs_source ) -> list[str]:
        screenshot_filters = []
        
        if obspython.obs_source_filter_count( source ) == 0:
            return screenshot_filters
        
        with ObsTools.save_source( source ) as source_data:
            with ObsTools.access_array_in_data( source_data, "filters" ) as obs_array:
                count = obspython.obs_data_array_count( obs_array )
                for i in range( 0, count ):
                    with ObsTools.access_item_of_data_array( obs_array, i ) as filter_data:
                        name : str = obspython.obs_data_get_string( filter_data, "name" )
                        if name.startswith( self._SNAPSHOT_FILTER_INSTANCE_NAME ):
                            screenshot_filters.append( name )

        return screenshot_filters
    
    def remove_screenshot_filters( self ) -> None:
        with ObsTools.access_sources() as source_list:
            for source in source_list:
                for screenshot_filter_name in self.get_screenshot_filter_names_from_source( source ):
                    with ObsTools.access_source_filter_by_name( source, screenshot_filter_name ) as obs_filter:
                        if obs_filter is not None:
                            obspython.obs_source_filter_remove( source, obs_filter )

snapshotter = SnapshotPopper()

# Called at script load
def script_load(settings):
    snapshotter.load(settings)

# Description displayed in the Scripts dialog window
def script_description():
    return snapshotter.description()

# Called to set default values of data settings
def script_defaults(settings):
    snapshotter.defaults(settings)

# Called to display the properties GUI
def script_properties():
    return snapshotter.properties()

# Called after change of settings including once after script load
def script_update(settings):
    snapshotter.update(settings)

# Called before data settings are saved
def script_save(settings):
    snapshotter.save(settings)

# Called at script unload
def script_unload():
    snapshotter.unload()
